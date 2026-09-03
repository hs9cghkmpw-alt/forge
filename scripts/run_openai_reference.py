#!/usr/bin/env python3
"""OpenAI Reference Judge を**明示実行**する開発用 CLI。

例 (Windows PowerShell):

    $env:OPENAI_API_KEY = "<secret>"
    $env:FORGE_ALLOW_REAL_PROVIDER_CALLS = "1"
    python scripts/run_openai_reference.py `
      --request-file request.txt `
      --candidate-file candidate.json `
      --target-contract-file target.json `
      --acknowledge-cloud-data

API key は表示・保存しない。入力データは OpenAI API へ送信されるため、
``--acknowledge-cloud-data`` を必須にする。さらに Backend 共通の
Default Deny により ``FORGE_ALLOW_REAL_PROVIDER_CALLS=1`` も必要。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ai.reference.openai_reference import (  # noqa: E402
    OPENAI_API_KEY_ENV,
    OpenAIReferenceProvider,
    judge_candidate,
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Forge Candidate を OpenAI Reference で評価する。"
            "Reference 判定は Teacher Candidate であり Truth / 99_PROVEN ではない。"
        )
    )
    parser.add_argument("--request-file", type=Path, required=True)
    parser.add_argument("--candidate-file", type=Path, required=True)
    parser.add_argument("--target-contract-file", type=Path, required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--acknowledge-cloud-data",
        action="store_true",
        help="指定した3ファイルの内容を外部OpenAI APIへ送ることを明示承認する",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()

    if not args.acknowledge_cloud_data:
        print(
            "REFUSED: 外部APIへデータを送るため --acknowledge-cloud-data が必要です。",
            file=sys.stderr,
        )
        return 2

    if not os.environ.get(OPENAI_API_KEY_ENV, "").strip():
        print(
            f"REFUSED: {OPENAI_API_KEY_ENV} が設定されていません。キー本体は引数や"
            "ファイルへ書かず、環境変数に設定してください。",
            file=sys.stderr,
        )
        return 2

    request_text = args.request_file.read_text(encoding="utf-8")
    candidate = _read_json(args.candidate_file)
    target_contract = _read_json(args.target_contract_file)

    provider = OpenAIReferenceProvider(model=args.model)
    assessment = judge_candidate(
        provider,
        request_text=request_text,
        candidate=candidate,
        target_contract=target_contract,
    )
    result = {
        "evidence_kind": "external_reference_candidate",
        "provider": provider.provider_name,
        "model": provider.model,
        "assessment": assessment,
        "certification_effect": "none",
        "warning": (
            "OpenAI Reference は独立校正候補であり、単独では VERIFIED / "
            "99_PROVEN / HARD_GATE_PROVEN の根拠にならない"
        ),
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Reference result written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
