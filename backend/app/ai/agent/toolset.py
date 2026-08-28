"""Forge の標準 Toolset — **道具を1箇所で組み立てる**
(FORGE-020 §14、2026-08-25)。

---

## なぜ組み立てを1箇所にするのか

道具の登録が呼び出し側に散ると、**呼び出し側ごとに違う道具立て**が
できる。ある経路では `write_file` が sandbox 外で登録され、別の経路では
`fetch_url` だけ抜けている、という形になる。

Forge が5回繰り返した「作ったが本番から呼ばれない」の親戚である
——「本番ごとに違うものが呼ばれる」。**組み立ては1つにする。**

## shell を渡さない

`run_build` / `run_test` / `run_lint` は**Forge が持つコマンド**を
呼ぶ。Model が渡せるのは「どれを走らせるか」だけで、
コマンド文字列そのものではない（§14）。
"""

from __future__ import annotations

import json
import shlex
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.ai.agent.permission import PermissionBroker
from app.ai.agent.sandbox import ToolSandbox
from app.ai.agent.tools import ToolBroker, ToolSpec
from app.ai.agent.untrusted import UntrustedContent
from app.ai.agent.web import WebFetcher, WebFetchError, WebSearchTool

__all__ = [
    "CommandRunner",
    "build_default_toolset",
    "build_generation_inspection_toolset",
]


@dataclass
class CommandRunner:
    """**あらかじめ決めたコマンドだけ**を走らせる（§14）。

    Model が名前で選ぶ。コマンド文字列は Forge が持つ。任意の shell
    文字列を受け取る口をここに作らない。
    """

    sandbox: ToolSandbox
    commands: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    timeout_seconds: float = 300.0
    max_output_chars: int = 20_000

    def run(self, name: str) -> str:
        argv = self.commands.get(name)
        if argv is None:
            # **知らないコマンドは走らせない。** Model が名前を作っても届かない。
            msg = f"未登録のコマンド: {name}"
            raise ValueError(msg)
        try:
            completed = subprocess.run(  # noqa: S603 — argv は Forge が持つ固定値
                list(argv), cwd=self.sandbox.root, capture_output=True,
                text=True, timeout=self.timeout_seconds, check=False,
            )
        except subprocess.TimeoutExpired:
            return f"[timeout] {shlex.join(argv)} は {self.timeout_seconds}s で終わらなかった"
        output = (completed.stdout + completed.stderr)[: self.max_output_chars]
        return f"[exit {completed.returncode}]\n{output}"


def build_default_toolset(
    *,
    sandbox: ToolSandbox,
    permissions: PermissionBroker | None = None,
    in_sandbox: bool = True,
    confirmed_tools: frozenset[str] = frozenset(),
    search: WebSearchTool | None = None,
    fetcher: WebFetcher | None = None,
    runner: CommandRunner | None = None,
) -> ToolBroker:
    """本番が使う道具立て。**ここを通らない道具を Agent へ渡さない。**"""
    broker = ToolBroker(
        permissions=permissions, in_sandbox=in_sandbox,
        confirmed_tools=confirmed_tools,
    )

    # -- repository を読む -------------------------------------------------
    broker.register(ToolSpec(
        name="read_file",
        description="作業領域の中の file を読む（secret を含む path は拒否）",
        required=("path",), run=lambda path: sandbox.read_text(path),
    ))
    broker.register(ToolSpec(
        name="list_files",
        description="作業領域の中の directory を一覧する",
        optional=("path",),
        run=lambda path=".": "\n".join(sandbox.list_files(path)),
    ))
    broker.register(ToolSpec(
        name="search_code",
        description="作業領域の中を文字列で検索する",
        required=("query",), optional=("path",),
        run=lambda query, path=".": _search(sandbox, query, path),
    ))
    broker.register(ToolSpec(
        name="write_file",
        description="作業領域の中へ file を書く（sandbox の外は拒否）",
        required=("path", "content"),
        run=lambda path, content: str(sandbox.write_text(path, content)),
    ))

    # -- 走らせる -----------------------------------------------------------
    if runner is not None:
        for tool_name in ("run_build", "run_test", "run_lint", "run_app"):
            if tool_name in runner.commands:
                broker.register(ToolSpec(
                    name=tool_name,
                    description=f"あらかじめ登録された {tool_name} を実行する",
                    run=(lambda captured: lambda: runner.run(captured))(tool_name),
                ))
        if "git_diff" in runner.commands:
            broker.register(ToolSpec(
                name="git_diff", description="作業領域の差分を見る",
                run=lambda: runner.run("git_diff"),
            ))

    # -- Web ---------------------------------------------------------------
    if search is not None:
        broker.register(ToolSpec(
            name="web_search",
            description="公開Webを検索する（出典付き。Provider未設定なら0件）",
            required=("query",), optional=("limit",),
            run=lambda query, limit=5: _render_search(search, query, int(limit)),
        ))
    if fetcher is not None:
        broker.register(ToolSpec(
            name="fetch_url",
            description="公開ページを取得する（本文は参考資料として扱われる）",
            required=("url",),
            run=lambda url: _render_fetch(fetcher, url),
        ))
    return broker


def _search(sandbox: ToolSandbox, query: str, path: str) -> str:
    root = sandbox.resolve(path)
    hits: list[str] = []
    for candidate in sorted(root.rglob("*")):
        if not candidate.is_file():
            continue
        if not sandbox.contains(candidate):
            continue
        try:
            text = candidate.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if query in line:
                hits.append(f"{candidate.relative_to(sandbox.root)}:{number}: {line.strip()}")
                if len(hits) >= 200:
                    return "\n".join(hits)
    return "\n".join(hits)


def _render_search(search: WebSearchTool, query: str, limit: int) -> str:
    results = search.search(query, limit=limit)
    if not results:
        # **作り話をしない。** 「Providerが無い」と正直に言う。
        return (
            "検索結果は0件（Search Provider が設定されていない）。"
            "推測でURLや内容を作らないこと。"
        )
    return "\n\n".join(
        f"[{r.source_domain}] {r.title}\n{r.url}\n{r.snippet}" for r in results
    )


def _render_fetch(fetcher: WebFetcher, url: str) -> str:
    try:
        content: UntrustedContent = fetcher.fetch(url)
    except WebFetchError as error:
        return f"[fetch_failed:{error.kind}] {url}"
    # **必ず包みを通す。** 素の本文をここから返さない。
    return content.as_reference_material()



def build_generation_inspection_toolset(
    *,
    forge_document: dict,
    capability_gap: object,
    validator,
    permissions: PermissionBroker | None = None,
) -> ToolBroker:
    """FORGE-020B production toolset.

    The Local Agent does not receive the Forge server repository or arbitrary shell.
    It can inspect only structural facts about the generated document, capability
    identifiers, and a fresh deterministic Validator result. Tool outputs deliberately
    exclude document values, user text, prompts, and validation messages.
    """
    broker = ToolBroker(permissions=permissions, in_sandbox=False)
    broker.register(ToolSpec(
        name="inspect_forge_document",
        description="生成済みForge Documentの構造件数だけを調べる",
        run=lambda: json.dumps(_document_structure_summary(forge_document), sort_keys=True),
    ))
    broker.register(ToolSpec(
        name="validate_forge_document",
        description="Forge Validatorを再実行し、合否と分類件数だけを見る",
        run=lambda: json.dumps(_validation_summary(validator(forge_document)), sort_keys=True),
    ))
    broker.register(ToolSpec(
        name="inspect_capability_gap",
        description="不足・部分対応CapabilityのIDと完了阻害フラグだけを見る",
        run=lambda: json.dumps(_capability_gap_summary(capability_gap), sort_keys=True),
    ))
    return broker


def _document_structure_summary(document: dict) -> dict[str, object]:
    widget_types: dict[str, int] = {}
    action_count = 0
    state_count = 0

    def walk(value: object) -> None:
        nonlocal action_count, state_count
        if isinstance(value, dict):
            kind = value.get("type")
            if isinstance(kind, str):
                widget_types[kind] = widget_types.get(kind, 0) + 1
            if "action" in value or "actions" in value:
                action_count += 1
            for key, child in value.items():
                if key == "state":
                    if isinstance(child, dict):
                        state_count += len(child)
                    elif isinstance(child, list):
                        state_count += len(child)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(document)
    screens = document.get("screens", ())
    return {
        "forge_language_version": str(document.get("version", "") or ""),
        "screen_count": len(screens) if isinstance(screens, list) else 0,
        "widget_count": sum(widget_types.values()),
        "widget_types": dict(sorted(widget_types.items())),
        "action_container_count": action_count,
        "state_entry_count": state_count,
    }


def _validation_summary(validation: object) -> dict[str, object]:
    errors = tuple(getattr(validation, "errors", ()) or ())
    warnings = tuple(getattr(validation, "warnings", ()) or ())
    return {
        "valid": bool(getattr(validation, "valid", False)),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "error_categories": sorted({
            str(getattr(item, "category", "") or "") for item in errors
            if getattr(item, "category", "")
        }),
        "warning_categories": sorted({
            str(getattr(item, "category", "") or "") for item in warnings
            if getattr(item, "category", "")
        }),
    }


def _capability_gap_summary(gap: object) -> dict[str, object]:
    return {
        "missing": list(getattr(gap, "missing", ()) or ()),
        "partial": list(getattr(gap, "partial", ()) or ()),
        "critical": list(getattr(gap, "critical", ()) or ()),
        "blocks_completion": bool(getattr(gap, "blocks_completion", False)),
    }
