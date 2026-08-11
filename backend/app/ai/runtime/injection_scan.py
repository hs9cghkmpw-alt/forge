"""Prompt Injection Guard(`forge_ai/`)への薄いAdapter
(FORGE-AI-CONNECT-001 TD21対応、2026-08-11)。

`prompt_pipeline.py`は`run_cognitive_pipeline`・`RepairEngine`・
`QualityEngine`の3つに限りforge_ai/を直接importしてよいという既存の
制約を持つ(同ファイル冒頭のdocstring、`test_ai_runtime.py`の
`test_prompt_pipeline_module_does_not_import_individual_m004_components`
参照)。Prompt Injection Guardの呼び出しをこの制約の対象にしないため、
`forge_ai_adapter.py`・`forge_ai_provider_bridge.py`と同じ「Adapter層の
みがforge_ai/へ依存する」という既存パターンを踏襲し、独立したこの
ファイルへ切り出す。
"""

from __future__ import annotations

from typing import Any

from forge_ai.prompt.injection_guard import PromptInjectionGuard


def scan_for_injection(natural_language: str) -> dict[str, Any]:
    """ユーザーの自然言語入力をInjection Guardへ通し、診断用途のdictへ
    変換する。**検出のみを行い、ブロックはしない**(呼び出し側
    (`routers/ai.py`)がdiagnosticsとして記録するだけで、リクエスト自体は
    最後まで処理する。`forge_ai/prompt/injection_guard.py`の設計方針
    そのまま)。
    """
    report = PromptInjectionGuard().scan(natural_language)
    return {
        "detected": report.detected,
        "signals": [
            {"category": s.category, "matched_phrase": s.matched_phrase} for s in report.signals
        ],
    }
