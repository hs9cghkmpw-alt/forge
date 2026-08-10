# Task022 — FORGE-MILESTONE-004: Forge AI v0.1 (Cognitive Engine) 正式提出

## 依頼内容
「FORGE-MILESTONE-004を開始してください。目的はForge AI v0.1（Cognitive
Engine）の基盤構築です。LLM非依存・Mock Provider前提で、Domain Model・
World Model・Meaning Model・Intent Model・Plannerを実装してください。
Runtime・Flutter・Backend API・実LLM接続は今回は対象外です。設計を
固定してから実装し、Unit Testを含めて提出してください。」という依頼を受けた。

## 事実確認
依頼を受けた時点で、`forge_ai/`にはこの依頼内容と完全に一致する実装が
既に存在していた(Domain Model・World Model・Meaning Model・Intent Model・
Planner、加えてCompiler・Repair Engine・Quality Engine・Provider
Interface・Prompt Builder・Contracts、80件のテスト全合格)。これは
「FORGE PROJECT — AI実装チーム キックオフ指示書」に基づき、以前の
セッションで実装されたものである。

また、`docs/reports/FORGE-MILESTONE-004-report.md`という、同じ
「FORGE-MILESTONE-004」という名前で、しかし異なる内容(2026-07-13付
「Native AI Phase-1（Intent Engine）」、`backend/app/ai/runtime/`拡張)の
報告書が既に存在することを確認した。前回のFORGE-MILESTONE-003.1で
このファイル群を「由来不明」と報告していたが、実際には
`docs/DECISIONS.md` D50〜D55・`TECH_DEBT.md` TD20〜TD22という正規の
記録があったため、この報告を訂正した。

## 行ったこと
ゼロから再実装するのではなく、既存実装を検証・強化した上でM004の
正式提出物として採用した。

- `forge_ai/`全20ソースファイルのimport文を再監査し、LLM SDK・Flutter・
  Backend APIへの依存が無いことを確認した(標準ライブラリと
  forge_ai内部モジュールのみ)。
- `py_compile`で構文エラー0件を再確認した。
- `ast`による静的解析で、型ヒント・Docstringが100%であることを再確認した。
- 80件のUnit Testを再実行し、全件合格を再確認した。
- `forge_ai/docs/DESIGN_DECISIONS.md`にD6を追加し、今回の経緯と、
  他のNative AI関連コードとの関係(未整理のまま残っていること)を記録した。
- `docs/spec/NATIVE_AI_STATUS_NOTE.md`を更新した。

## 変更理由
「後出しをしない」「無条件に同意しない」という基本姿勢に従い、依頼された
スコープと完全に一致する実装が既に存在するという事実を、実装を始める前に
まず確認し、CEOへ明示的に報告することを優先した。重複した実装を新たに
作ることは、既存の検証済みコードを無駄にするだけでなく、
`backend/app/ai/native/`・`backend/app/ai/runtime/`という既存の別実装と
合わせて「Native AI関連の実装が4つ目」になってしまうリスクがあり、
混乱を増やすだけだと判断した。
