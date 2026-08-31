"""**獲得した Capability を Forge の Flutter アプリまで通す**（TD94）。

---

## 何を通すか

```text
未知の要求
  → Capability Plan が gap を名指しする           (view.calendar が missing)
  → 実装を生成する                                 (Dart)
  → 隔離 workspace で実 dart による試験・解析・起動確認
  → PROMOTED
  → Forge の Flutter アプリへ install               ← ここが TD94
  → 生成 Document を本番 compiler で作る
  → Flutter が Parser → Registry → 実 Widget まで解決する
```

最後の1行は Dart 側で確かめる（`frontend/test_acquired/`）。
この script はそこまでの下ごしらえを**本番の関数で**行い、
生成 Document を JSON として置く。

## 通らないものを通ったことにしない

各段で条件を確かめ、満たさなければ**即座に落とす**。
「install したつもり」「Document に出たつもり」を残さない。

## 秘密情報

Provider は Test Double である。実 API を呼ばない。
API キー・token の類は一切扱わない。
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forge_ai.core.ir.capability_document_contribution import (  # noqa: E402
    CapabilityDocumentContribution,
    register_document_contribution,
)
from forge_ai.core.ir.capability_ir import entity_spec_from_plan  # noqa: E402
from forge_ai.core.ir.forge_language_compiler import ForgeLanguageCompiler  # noqa: E402
from forge_ai.core.ir.ir_generator import IRGenerator  # noqa: E402
from forge_ai.core.orchestration.capability_artifact_synthesis import (  # noqa: E402
    CapabilityArtifactSynthesizer,
)
from forge_ai.core.orchestration.extension_manifest import (  # noqa: E402
    ExtensionManifest,
    ExtensionStatus,
)
from forge_ai.core.orchestration.extension_plan import ExtensionRoute  # noqa: E402
from forge_ai.core.orchestration.flutter_capability_installer import (  # noqa: E402
    INSTALL_ROOT,
    FlutterCapabilityInstaller,
    verify_installed_capability,
)
from forge_ai.core.orchestration.synthesizing_build_time_implementer import (  # noqa: E402
    SynthesizingBuildTimeImplementer,
    build_plan_for_language,
)
from forge_ai.core.semantics.capability_plan import plan_capabilities  # noqa: E402
from forge_ai.provider.provider_interface import ProviderResponse  # noqa: E402
from scripts._acquired_calendar_source import (  # noqa: E402
    CALENDAR_CONTRACT as CONTRACT,
)
from scripts._acquired_calendar_source import (  # noqa: E402
    CALENDAR_PAYLOAD,
)

FRONTEND = ROOT / "frontend"
DOCUMENT_OUT = FRONTEND / "test_acquired" / "generated_document.json"

NEED = "通院の記録を残して、日付をカレンダーで確認したい"
CAPABILITY = "view.calendar"
WIDGET_TYPE = "calendar_view"

class _TestDoubleProvider:
    """**実 Model ではない。** 実 Model が書いた証拠はまだ無い。"""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt):  # noqa: ANN001, ANN202
        self.calls += 1
        return ProviderResponse(text="", structured=CALENDAR_PAYLOAD)


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def restore() -> None:
    """獲得物を取り除き、登録表を出荷状態へ戻す。"""
    root = FRONTEND / INSTALL_ROOT
    for entry in sorted(root.iterdir()):
        if entry.is_dir():
            shutil.rmtree(entry)
    installer = FlutterCapabilityInstaller(
        frontend_root=FRONTEND, harness_files=frozenset(),
    )
    installer.rewrite_registrations()
    if DOCUMENT_OUT.exists():
        DOCUMENT_OUT.unlink()
    print("restored: no acquired capability is installed")


def main() -> None:
    if "--restore" in sys.argv:
        restore()
        return

    print("=== BEFORE: Capability Plan ===")
    plan = plan_capabilities(NEED)
    print(f"  need    : {NEED}")
    print(f"  missing : {plan.missing}")
    if CAPABILITY not in plan.missing:
        _fail(f"{CAPABILITY} should be missing before acquisition; got {plan.missing}")

    print("=== 生成 → 実 dart による試験・解析・起動確認 → PROMOTED ===")
    provider = _TestDoubleProvider()
    implementer = SynthesizingBuildTimeImplementer(
        synthesizer=CapabilityArtifactSynthesizer(provider=provider),
        contract_for=lambda _capability_id: CONTRACT,
        known_source_digests=frozenset(),
    )
    manifest = ExtensionManifest(
        capability_id=CAPABILITY, label_ja="カレンダーで見る",
        route=ExtensionRoute.BUILD_TIME, requires_confirmation=False,
    )
    implementation = implementer(manifest)
    execution = implementer.last_execution
    if execution is None:
        _fail("no managed build execution was recorded")
    for kind in ("test", "build", "runtime_probe"):
        if not execution.evidence.passed(kind):
            _fail(f"{kind} did not pass in the isolated dart workspace")
        print(f"  {kind:<14} exit=0")
    if implementation.manifest.status is not ExtensionStatus.PROMOTED:
        _fail(f"manifest is {implementation.manifest.status}, not PROMOTED")
    if implementation.activation is None or not implementation.activation.loaded:
        _fail("no loaded activation")
    print(f"  PROMOTED  build_id={implementation.activation.build_id}")

    print("=== install: Forge の Flutter アプリへ載せる ===")
    plan_for_dart = build_plan_for_language(CONTRACT.host_language)
    installer = FlutterCapabilityInstaller(
        frontend_root=FRONTEND,
        harness_files=frozenset(
            (*plan_for_dart.harness_files, "capability_contribution.json"),
        ),
        host_prefix=plan_for_dart.host_prefix,
    )
    # **作り直さない。** 検査を通ったそのものを載せる
    #（作り直した瞬間、検査した対象と動く対象が別物になる）。
    verified = implementer.last_verified
    if verified is None:
        _fail("no verified artifact was retained by the implementer")
    artifact = verified.artifact
    installation = installer.install(verified)
    registrations = installer.rewrite_registrations()
    for path in installation.installed_files:
        print(f"  installed  {path}")
    print(f"  registrations rewritten: {registrations.relative_to(ROOT)}")
    body = registrations.read_text(encoding="utf-8")
    if installation.slug not in body:
        _fail("the regenerated registration table does not mention the capability")
    installed_digest = verify_installed_capability(FRONTEND, installation.slug)
    if installed_digest != verified.source_digest:
        _fail("installed source digest differs from the inspected artifact")
    print(f"  検査した生成物 = 載せた生成物: {installed_digest[:16]}…")

    print("=== 生成 Document（本番 compiler） ===")
    declaration = json.loads(
        next(f.content for f in artifact.files if f.path == "capability_contribution.json"),
    )
    register_document_contribution(CapabilityDocumentContribution(
        capability_id=declaration["capability_id"],
        widget_type=declaration["widget_type"],
        widget_id=declaration["widget_id"],
        document_version=declaration["document_version"],
        properties=tuple((key, value) for key, value in declaration["properties"]),
        fallback_container_id=declaration.get("fallback_container_id", "contribution_root"),
    ))
    spec = entity_spec_from_plan(plan)
    if spec is None:
        _fail("the plan produced no entity spec")
    document = ForgeLanguageCompiler().compile(
        IRGenerator().build_from_spec(spec),
        domain_category="generic",
        title="通院の記録",
        promoted_capabilities=(CAPABILITY,),
    )
    payload = document.to_json_dict()
    types = json.dumps(payload, ensure_ascii=False)
    if f'"{WIDGET_TYPE}"' not in types:
        _fail(f"the compiled document does not contain {WIDGET_TYPE!r}")
    DOCUMENT_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOCUMENT_OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"  {WIDGET_TYPE} is in the compiled document")
    print(f"  written: {DOCUMENT_OUT.relative_to(ROOT)}")

    print("=== まだ言えないこと ===")
    print("  実 Model が書いた証拠は無い（Provider は Test Double）")
    print("  Real Local Model runs = 0 のまま")
    print("  Flutter が実際に描くかどうかは frontend/test_acquired/ が確かめる")


if __name__ == "__main__":
    main()
