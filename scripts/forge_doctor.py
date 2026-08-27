"""**このPCで何が検証できるか**を調べる（FORGE-020A1、2026-08-26）。

---

## なぜ要るのか

Forge には**常設の実行PCが無い**（`docs/MACHINE-INDEPENDENT-POLICY.md`）。
開発 container、CEO の手元、Reviewer の環境——**そのとき Local Model が
動くPCが、そのときだけ Execution Host になる。**

だから作業を始める前に「このPCでは何が測れて、何が測れないか」を
知る必要がある。知らずに始めると、

* 測れないものを「失敗した」と書く（Level 0 の INVALID_PROBE と同じ穴）
* 測れるのに測らないまま UNVERIFIED を据え置く

の両方が起きる。

## この script がやらないこと

* **何もインストールしない。** 読むだけである
* **何も設定を書き換えない。** 環境変数も PATH も触らない
* **秘密を出さない。** APIキーは「設定されているか」だけを見る。
  値も長さも先頭数文字も出さない（`CLAUDE.md` §4）

## 使い方

```
python scripts/forge_doctor.py          # 人が読む形
python scripts/forge_doctor.py --json   # 機械が読む形
```

終了コードは常に 0。**これは診断であって、判定ではない。**
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass

_TIMEOUT = 5.0

#: Local Model の Runtime としてありうるもの。**入れない。在るかだけ見る。**
_RUNTIME_COMMANDS = ("ollama", "llama-server", "llama-cli", "lms", "vllm")

#: 環境変数は**名前だけ**を扱う。値は読まない（`CLAUDE.md` §4）。
_SECRET_ENV_NAMES = (
    "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "FORGE_LOCAL_BASE_URL", "FORGE_LOCAL_MODEL",
)


@dataclass
class Finding:
    """1項目の診断結果。"""

    name: str
    available: bool
    detail: str = ""
    enables: str = ""
    """これが在ると**何が検証できるようになるか**。"""


def _which(command: str) -> str:
    return shutil.which(command) or ""


def _version_of(command: str, *args: str) -> str:
    path = _which(command)
    if not path:
        return ""
    try:
        result = subprocess.run(  # noqa: S603
            [path, *args], capture_output=True, text=True, timeout=_TIMEOUT, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (result.stdout or result.stderr).strip().splitlines()[0][:120] if (
        result.stdout or result.stderr
    ) else ""


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def _https_reachable(host: str) -> bool:
    """**読むだけ。** proxy を外したり TLS 検証を切ったりしない。"""
    try:
        import httpx  # noqa: PLC0415

        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            return client.head(f"https://{host}").status_code < 500
    except Exception:  # noqa: BLE001 — 到達不能も結果である
        return False


def collect() -> list[Finding]:
    findings: list[Finding] = []

    # -- 土台 ---------------------------------------------------------
    findings.append(Finding(
        "python", True, platform.python_version(),
        "backend / forge_ai のテスト",
    ))
    findings.append(Finding(
        "git", bool(_which("git")), _version_of("git", "--version"),
        "GitHub を Source of Truth として同期する",
    ))
    flutter = _which("flutter") or ("/opt/flutter/bin/flutter"
                                    if os.path.exists("/opt/flutter/bin/flutter") else "")
    findings.append(Finding(
        "flutter", bool(flutter), flutter,
        "Renderer のテスト・Web build・実描画",
    ))

    # -- 撮影 ---------------------------------------------------------
    browser = ""
    for candidate in ("/opt/pw-browsers/chromium", "chromium", "google-chrome"):
        browser = _which(candidate) if not candidate.startswith("/") else (
            candidate if os.path.exists(candidate) else ""
        )
        if browser:
            break
    playwright_installed = False
    try:
        import playwright  # noqa: F401, PLC0415

        playwright_installed = True
    except ImportError:
        pass
    findings.append(Finding(
        "browser", bool(browser and playwright_installed),
        f"browser={browser or '(無し)'} playwright={playwright_installed}",
        "Quality Gate v2 の実描画・撮影",
    ))

    # -- ネットワーク -------------------------------------------------
    for host, enables in (
        ("github.com", "push / fetch"),
        ("huggingface.co", "open-weight model の取得"),
        ("ollama.com", "Ollama の取得"),
    ):
        findings.append(Finding(f"net:{host}", _https_reachable(host), "", enables))

    # -- Local Model Runtime ------------------------------------------
    for command in _RUNTIME_COMMANDS:
        path = _which(command)
        if path:
            findings.append(Finding(
                f"runtime:{command}", True, path,
                "Level 0（実 Local Model の E2E）",
            ))
    if not any(f.name.startswith("runtime:") for f in findings):
        findings.append(Finding(
            "runtime", False, "Ollama / llama.cpp / LM Studio / vLLM のどれも無い",
            "Level 0（実 Local Model の E2E）",
        ))

    base_url = os.environ.get("FORGE_LOCAL_BASE_URL", "http://127.0.0.1:11434/v1")
    host = base_url.split("//", 1)[-1].split("/", 1)[0]
    hostname, _, port_text = host.partition(":")
    findings.append(Finding(
        "runtime:listening", _port_open(hostname or "127.0.0.1", int(port_text or 11434)),
        base_url, "Level 0（実 Local Model の E2E）",
    ))

    # -- GPU ----------------------------------------------------------
    findings.append(Finding(
        "gpu:nvidia", bool(_which("nvidia-smi")),
        _version_of("nvidia-smi", "--query-gpu=name", "--format=csv,noheader"),
        "実用的な速度での Level 0.5（Baseline Benchmark）",
    ))

    # -- 設定（**名前だけ**） -----------------------------------------
    for name in _SECRET_ENV_NAMES:
        findings.append(Finding(
            f"env:{name}", bool(os.environ.get(name)),
            # **値を出さない。長さも先頭数文字も出さない。**
            "設定あり" if os.environ.get(name) else "未設定",
            "Provider の自動検出",
        ))

    return findings


def verdict(findings: list[Finding]) -> dict[str, bool]:
    """**このPCで通せる検証。**"""
    have = {f.name: f.available for f in findings}
    runtime_present = any(
        available for name, available in have.items()
        if name.startswith("runtime:") and name != "runtime:listening"
    )
    return {
        "backend_and_forge_ai_tests": have.get("python", False),
        "renderer_tests": have.get("flutter", False),
        "quality_gate_visual": have.get("flutter", False) and have.get("browser", False),
        "github_sync": have.get("git", False) and have.get("net:github.com", False),
        "model_download": have.get("net:huggingface.co", False)
        or have.get("net:ollama.com", False),
        "level0_local_model": runtime_present and have.get("runtime:listening", False),
        # CPU benchmark is valid. GPU/VRAM characterize performance and viable
        # model size; they are evidence, never a prerequisite.
        "level0_5_baseline": runtime_present,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="このPCで何が検証できるかを調べる（読むだけ）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    findings = collect()
    can = verdict(findings)

    if args.json:
        print(json.dumps(
            {"host": socket.gethostname(), "platform": platform.platform(),
             "findings": [asdict(f) for f in findings], "can": can},
            ensure_ascii=False, indent=2,
        ))
        return 0

    print("=" * 68)
    print("Forge Doctor — このPCで何が検証できるか（インストールはしない）")
    print("=" * 68)
    print(f"  host: {socket.gethostname()}  ({platform.platform()})")
    print()
    for finding in findings:
        mark = "✓" if finding.available else "✗"
        print(f"  {mark} {finding.name:<28} {finding.detail}")
    print()
    print("-" * 68)
    print("  このPCで通せる検証")
    print("-" * 68)
    labels = {
        "backend_and_forge_ai_tests": "backend / forge_ai のテスト",
        "renderer_tests": "Renderer のテスト",
        "quality_gate_visual": "Quality Gate v2（実描画・撮影）",
        "github_sync": "GitHub 同期（push / fetch）",
        "model_download": "open-weight model の取得",
        "level0_local_model": "Level 0（実 Local Model の E2E）",
        "level0_5_baseline": "Level 0.5（Baseline Benchmark）",
    }
    for key, label in labels.items():
        print(f"  {'✓ 可' if can[key] else '✗ 不可'}  {label}")
    print()
    print("  **不可のものは UNVERIFIED のままにする。**")
    print("  出来ないことを「失敗した」と書かない（`CLAUDE.md` §3）。")
    if not can["level0_local_model"]:
        print()
        print("  Level 0 を測るには、Runtime が動いている必要がある。例:")
        print("    ollama serve && ollama pull qwen2.5:1.5b-instruct")
        print("    export FORGE_LOCAL_BASE_URL=http://127.0.0.1:11434/v1")
        print("    export FORGE_LOCAL_MODEL=qwen2.5:1.5b-instruct")
        print("    python scripts/verify_local_model_level0.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
