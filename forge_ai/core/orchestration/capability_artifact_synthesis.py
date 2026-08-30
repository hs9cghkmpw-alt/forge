"""**足りない Capability の実装 Source を、Forge 自身に書かせる**（020E）。

---

## ここが Self-Extension の本丸である

`build_time_extension.py` 以降——managed workspace / 実 test / 実 build /
runtime probe / exact build 照合 / PROMOTED / Registry install——は既に
在り、実 subprocess で証明されている。

**しかしその手前が無かった。**

`BuildTimeCapabilityArtifact` を組み立てている場所は、これまで
**テストの中にしか無かった**。つまり Forge は

* 足りない能力を**名指しできる**（Capability Gap）
* 与えられた実装を**検証して取り込める**（BUILD_TIME）

の両端を持ちながら、**その2つを繋ぐ「実装を作る」段が空いていた。**

このモジュールがその段である。

## Capability 専用の分岐を持たない

```python
if capability_id == "view.map":      # ← 絶対に書かない
    return hardcoded_map_source
```

これを一般機構として書いた時点で、Self-Extension は
「あらかじめ人が書いた実装の出し分け」になる。能力を1つ足すたびに人が
枝を足すなら、それは Template を増やすのと同じであり、
`GENERATIVE-SOFTWARE-DIRECTION.md` が禁じている形である。

このモジュールが受け取るのは **Canonical Catalog から機械的に引いた
契約だけ**である。capability id の文字列リテラルは1つも持たない
（`test_capability_artifact_synthesis.py` が静的に固定する）。

## 「既に在るコード」を「今 Forge が作った能力」と偽らない

一番危ういのはここである。Model へ実装を書かせると、**repo に既にある
実装をそのまま書き戻してくる**ことがある。それを通すと、

> 「Forge が view.map を自律生成した」

という**嘘の実績**になる。実際には既存コードの activation でしかない。

そこで `known_source_digests` を**必須引数**にした。既存の出荷済み
Source の digest を渡さない呼び出しは、そもそも書けない。生成物が
既存ファイルと1バイトも違わなければ `PreexistingSourceError` で落とす。

**AI の出力を決して信用しない。** 通らなければ `None` を返す——
`entity_synthesizer.py` と同じ形である。作れなかったものを
「作れた」と言わない。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from forge_ai.core.orchestration.build_time_extension import (
    BuildTimeCapabilityArtifact,
    BuildTimeExtensionError,
    BuildTimeSourceFile,
)
from forge_ai.prompt.prompt_builder import PromptBuilder
from forge_ai.provider.provider_interface import AIProvider

__all__ = [
    "CapabilityArtifactSynthesizer",
    "CapabilityImplementationContract",
    "PreexistingSourceError",
    "digest_of_source",
]


class PreexistingSourceError(BuildTimeExtensionError):
    """**生成物が既存ファイルの丸写しだった。**

    これを通すと「既存コードの activation」が「自律生成した能力」に
    化ける。Self-Extension の実績として最も偽りやすい点なので、
    型で落とす。
    """


def digest_of_source(content: str) -> str:
    """既存 Source と生成 Source を突き合わせるための digest。

    改行コードと末尾空白だけの差で「別物」と判定されないよう、
    **正規化してから**取る。丸写しを緩く見逃さないためである。
    """
    normalized = "\n".join(line.rstrip() for line in content.replace("\r\n", "\n").split("\n"))
    return sha256(normalized.strip().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CapabilityImplementationContract:
    """**何を作らせるか。** Canonical Catalog から機械的に引く。

    ここに capability ごとの分岐は無い——どの能力でも同じ形の契約になる。
    """

    capability_id: str
    intent: str
    data_contract: tuple[str, ...]
    host_language: str
    binding_targets: tuple[str, ...]

    def validate(self) -> None:
        if not self.capability_id.strip():
            raise BuildTimeExtensionError("capability contract requires capability_id")
        if not self.intent.strip():
            raise BuildTimeExtensionError("capability contract requires intent")
        if not self.host_language.strip():
            raise BuildTimeExtensionError("capability contract requires host_language")
        if not self.binding_targets:
            raise BuildTimeExtensionError("capability contract requires binding targets")


#: 生成結果として受け取ってよい構造。
_MAX_FILES = 24
_MAX_BYTES_PER_FILE = 200_000
_SAFE_PATH = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]*$")


@dataclass(slots=True)
class CapabilityArtifactSynthesizer:
    """Capability Gap から **実装 Source Artifact** を作る。

    Capability を知らない。契約だけを見る。
    """

    provider: AIProvider
    prompt_builder: PromptBuilder = PromptBuilder()

    def synthesize(
        self,
        contract: CapabilityImplementationContract,
        *,
        known_source_digests: frozenset[str],
    ) -> BuildTimeCapabilityArtifact | None:
        """実装 Artifact を作る。**作れなければ `None`。**

        `known_source_digests` は既存の出荷済み Source の digest である。
        **既定値を持たせていない**——渡し忘れた呼び出しは書けない。
        既存コードの丸写しを「生成」と数えないための唯一の砦なので、
        忘れられる形にしない（`CLAUDE.md` §3）。
        """
        contract.validate()
        prompt = self.prompt_builder.build_capability_implementation_prompt(
            capability_id=contract.capability_id,
            capability_intent=contract.intent,
            data_contract=contract.data_contract,
            host_language=contract.host_language,
            binding_targets=contract.binding_targets,
        )
        response = self.provider.complete(prompt)
        structured = response.structured if isinstance(response.structured, dict) else {}

        files = self._sanitize_files(structured.get("files"))
        if not files:
            return None

        # **既存コードの書き戻しを弾く。**
        for source in files:
            if digest_of_source(source.content) in known_source_digests:
                raise PreexistingSourceError(
                    "generated source is byte-identical to existing shipped source: "
                    f"{source.path!r}. これは既存能力の activation であって、"
                    "新しく生成した能力ではない",
                )

        artifact = BuildTimeCapabilityArtifact(
            # **identity は契約側が持つ。** AI の自己申告を採らない
            # ——途中で別の能力へすり替わるのを防ぐ。
            capability_id=contract.capability_id,
            files=files,
            reusable_contract=self._sanitize_contract(structured.get("reusable_contract"), contract),
            changed_bindings=tuple(contract.binding_targets),
        )
        try:
            artifact.validate()
        except BuildTimeExtensionError:
            # **通らないものを「作れた」と言わない。**
            return None
        return artifact

    def _sanitize_files(self, raw: Any) -> tuple[BuildTimeSourceFile, ...]:
        if not isinstance(raw, list) or not raw:
            return ()
        collected: list[BuildTimeSourceFile] = []
        seen: set[str] = set()
        for entry in raw[:_MAX_FILES]:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            content = entry.get("content")
            if not isinstance(path, str) or not isinstance(content, str):
                continue
            path = path.strip()
            # **絶対パスを相対へ「直して」通さない。**
            #
            # 以前ここは `lstrip("/")` していた。`/abs/path.dart` が
            # `abs/path.dart` になって**通ってしまう**。怪しい入力を
            # 正規化して受け入れるのは、楽観側へ倒すことである
            # （`CLAUDE.md` §3）。落とす。
            if path.startswith("/") or path.startswith("\\"):
                continue
            if not path or not _SAFE_PATH.match(path) or ".." in path.split("/"):
                continue
            if len(content.encode("utf-8")) > _MAX_BYTES_PER_FILE:
                continue
            if not content.strip() or path in seen:
                continue
            seen.add(path)
            collected.append(BuildTimeSourceFile(path=path, content=content))
        # **実装だけ / テストだけ は受け取らない。**
        # 検証できない実装は、通っても「動いた」の証拠にならない。
        if not any("test" in item.path.lower() for item in collected):
            return ()
        if not any("test" not in item.path.lower() for item in collected):
            return ()
        return tuple(collected)

    def _sanitize_contract(
        self, raw: Any, contract: CapabilityImplementationContract,
    ) -> str:
        """再利用契約の文。空なら**契約から決定的に組む**。

        ここで空文字を通すと `artifact.validate()` が落ちて `None` に
        なる。AI が説明文を書き忘れただけで実装を捨てるのは惜しいので、
        意味を変えない範囲で機械的に埋める。
        """
        if isinstance(raw, str) and raw.strip():
            return raw.strip()[:2000]
        inputs = ", ".join(contract.data_contract) or "(なし)"
        return (
            f"{contract.capability_id}: {contract.intent}"
            f"（入力: {inputs} / 実装言語: {contract.host_language}）"
        )
