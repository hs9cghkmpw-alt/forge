"""**実機で、どの段が何秒かかるのかを分けて測る。**

---

## 何のためか

実機（Ollama + `qwen2.5:1.5b-instruct`）で `/api/v1/ai/converse` が
**73.54 秒**かかった。会話の判定を速い道へ逃がして、そこは 0.09 ミリ秒に
なった。

**しかしそれは「ASK か BUILD か」を決めるところだけの数字である。**
そのあと `PromptPipeline` が実際に画面を作る。**そこが何秒かは、まだ
誰も測っていない。**

合計だけを見て「速くなった」と丸めないために、段ごとに分けて測る。

## 使い方（実機で）

Backend を起動した状態で:

```bash
python3 scripts/measure_real_device_converse.py
```

Backend が別の場所なら `--base-url http://127.0.0.1:8000` を渡す。
Provider を変えるなら `--provider local`（既定）。

結果は画面と `logs/forge-real-device-converse-<日時>.json` に残る。

## 遅かったときにやってはいけないこと

**timeout を伸ばして「解決」にしない。** この script は
`--timeout` を持つが、それは**測り切るため**であって、遅さを許すため
ではない。遅い段が分かったら、そこを速くする。

## 秘密情報

API キー・token を引数にも出力にも載せない。Provider 名と
`simulated` だけを見る。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: 実機で 73.54 秒かかり、しかも記録項目を聞き返した文（CEO 指定）。
REAL_DEVICE_CASE = "事務所の鍵を誰が持ち出していて、いつ返す予定なのか記録できるようにしたい"

#: 共有範囲という**本当に確かめるべきこと**がある文（CEO 指定）。
#: 速い道のために雑に BUILD しないことを確かめる。
SHARED_USAGE_CASE = "家族で予定を管理したい"

CASES = (
    ("A. 実機で落ちた文（BUILD へ進み、記録項目を聞き返さないこと）", REAL_DEVICE_CASE, "build"),
    ("B. 共有範囲が未確定な文（雑に BUILD せず、聞けること）", SHARED_USAGE_CASE, "ask_or_confirm"),
)


def _post(base_url: str, message: str, provider: str, timeout: float) -> dict:
    import httpx  # noqa: PLC0415 — backend の依存

    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{base_url.rstrip('/')}/api/v1/ai/converse",
                json={"message": message, "provider": provider},
            )
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 1)
        return {
            "http_status": response.status_code,
            "http_total_ms": elapsed_ms,
            "body": response.json(),
        }
    except Exception as exc:  # noqa: BLE001 — 落ちた事実も証拠である
        return {
            "http_status": None,
            "http_total_ms": round((time.perf_counter() - started) * 1000.0, 1),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _describe(outcome: dict) -> dict:
    """応答から、報告に要るものだけを取り出す。"""
    body = outcome.get("body") or {}
    timings = body.get("timings") or {}
    stages = timings.get("stages_ms") or {}
    counters = timings.get("counters") or {}
    notes = timings.get("notes") or {}
    result = body.get("result") or {}
    document = result.get("forge_document") if isinstance(result, dict) else None
    validation = (result.get("validation") or {}) if isinstance(result, dict) else {}

    return {
        "http_status": outcome.get("http_status"),
        "http_total_ms": outcome.get("http_total_ms"),
        "error": outcome.get("error"),
        "status": body.get("status"),
        "provider_used": body.get("provider"),
        "simulated": body.get("simulated"),
        "question": body.get("question"),
        # --- 段ごとの実測 ---
        "fast_path_ms": stages.get("fast_path"),
        "conversation_step_ms": stages.get("conversation_step"),
        "conversation_llm_ms": stages.get("conversation_llm"),
        "build_pipeline_ms": stages.get("build_pipeline"),
        "validator_ms": stages.get("validator"),
        # --- 回数 ---
        "conversation_llm_calls": counters.get("conversation_llm_calls", 0),
        "build_pipeline_runs": counters.get("build_pipeline_runs", 0),
        "validator_calls": (timings.get("stage_calls") or {}).get("validator", 0),
        "fast_path_taken": notes.get("fast_path_taken"),
        "fast_path_reason": notes.get("fast_path_reason"),
        # --- 生成物 ---
        "document_returned": bool(document),
        "document_screens": len((document or {}).get("screens") or []),
        "validation_valid": validation.get("valid"),
        "blocking_unknowns": len(
            (body.get("need_model") or {}).get("unknowns") or [],
        ),
    }


def _print_case(label: str, expectation: str, seen: dict) -> list[str]:
    """人が読める形で出しつつ、判定に失敗したものを返す。"""
    print(f"\n=== {label} ===")
    if seen["error"]:
        print(f"  **通信に失敗** {seen['error']}  ({seen['http_total_ms']} ms)")
        return [f"{label}: {seen['error']}"]

    print(f"  HTTP {seen['http_status']}  status={seen['status']}")
    print(f"  provider_used={seen['provider_used']}  simulated={seen['simulated']}")
    print(f"  速い道: {seen['fast_path_taken']}  理由: {seen['fast_path_reason']}")
    print("  --- 段ごとの実測 ---")
    for key, name in (
        ("fast_path_ms", "速い道の判定"),
        ("conversation_step_ms", "会話ステップ全体"),
        ("conversation_llm_ms", "会話の LLM 呼び出し"),
        ("build_pipeline_ms", "生成（PromptPipeline）"),
        ("validator_ms", "Validator"),
    ):
        value = seen[key]
        print(f"    {name:26} {'—' if value is None else f'{value} ms'}")
    print(f"    {'HTTP 全体':26} {seen['http_total_ms']} ms")
    print("  --- 回数 ---")
    print(f"    会話の LLM 呼び出し   {seen['conversation_llm_calls']}")
    print(f"    生成の実行           {seen['build_pipeline_runs']}")
    print(f"    Validator            {seen['validator_calls']}")
    print(f"  Forge Document が返ったか: {seen['document_returned']}"
          f"（画面 {seen['document_screens']} / Validator PASS={seen['validation_valid']}）")

    problems: list[str] = []
    if expectation == "build":
        if seen["status"] != "build":
            problems.append(
                f"{label}: status={seen['status']}（BUILD へ進んでいない）"
                + (f" / 聞き返した内容: {seen['question']!r}" if seen["question"] else ""),
            )
        elif not seen["document_returned"]:
            problems.append(f"{label}: BUILD だが Forge Document が返っていない")
    elif expectation == "ask_or_confirm":
        # `needs_confirmation` も「聞いた」側である
        # （Pipeline が確認を求めて止まった。黙って作ってはいない）。
        if seen["status"] not in ("ask", "confirm", "needs_confirmation"):
            problems.append(
                f"{label}: status={seen['status']}（共有範囲を確かめずに進んでいる）",
            )
    return problems


def _slowest(seen: dict) -> str:
    """**どの段が遅いのかを名指しする。** timeout を伸ばして誤魔化さない。"""
    candidates = {
        "生成（PromptPipeline）": seen.get("build_pipeline_ms"),
        "会話の LLM 呼び出し": seen.get("conversation_llm_ms"),
        "Validator": seen.get("validator_ms"),
        "速い道の判定": seen.get("fast_path_ms"),
    }
    measured = {k: v for k, v in candidates.items() if isinstance(v, (int, float))}
    if not measured:
        return "（段ごとの内訳が取れていない）"
    name = max(measured, key=lambda k: measured[k])
    return f"{name}（{measured[name]} ms）"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--provider", default="local")
    parser.add_argument(
        "--timeout", type=float, default=600.0,
        help="測り切るための上限。**遅さを許す値ではない。**",
    )
    args = parser.parse_args()

    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    print(f"base_url : {args.base_url}")
    print(f"provider : {args.provider}")
    print("（実 API キーは扱わない。provider 名と simulated だけを見る）")

    report: dict[str, object] = {
        "measured_at": stamp,
        "base_url": args.base_url,
        "provider_requested": args.provider,
        "cases": [],
    }
    problems: list[str] = []

    for label, message, expectation in CASES:
        seen = _describe(_post(args.base_url, message, args.provider, args.timeout))
        seen["input"] = message
        seen["label"] = label
        problems.extend(_print_case(label, expectation, seen))
        report["cases"].append(seen)

    out = ROOT / "logs" / f"forge-real-device-converse-{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"\nログ: {out.relative_to(ROOT)}")
    if any(
        isinstance(case, dict) and case.get("status") == "needs_confirmation"
        and case.get("fast_path_taken") is None
        for case in report["cases"]
    ):
        print(
            "\n注記: `needs_confirmation` の応答には段ごとの内訳が載らない"
            "（別の応答型を共有しているため）。**測れていないものを 0 と読まないこと。**",
        )

    first = report["cases"][0] if report["cases"] else {}
    if isinstance(first, dict) and not first.get("error"):
        print(f"\n一番遅い段: {_slowest(first)}")
        print("  ここが遅いなら、timeout を伸ばすのではなく**この段を速くする**。")

    if problems:
        print("\n=== 満たせなかったこと ===")
        for problem in problems:
            print(f"  - {problem}")
        raise SystemExit(1)
    print("\n2件とも期待どおり（BUILD へ進む / 共有範囲は確かめる）")


if __name__ == "__main__":
    main()
