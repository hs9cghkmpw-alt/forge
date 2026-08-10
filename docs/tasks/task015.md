# Task015 — FORGE-MILESTONE-003: Analyzer Zero → Chrome Verification → Native AI Foundation

## 依頼内容
CEO実測(Python 167 PASS・Flutter Test 212 PASS・Web Build PASS・Runtime/
Chrome/Mock Generator/Language v1.2/Widget v1.1/E2E全PASS)を前提に、
残る`flutter analyze`警告3件(Unused import・List inference・Map inference)
を解消し(PHASE1〜4)、Forge Native AI Foundation(`backend/app/ai/runtime/`
以下、Protocol定義+Stubのみ)を構築し(PHASE5〜9)、設計ドキュメント
(PHASE10)・Architecture Review(PHASE11)・技術的負債更新(PHASE12)を
行うことを依頼された。

## 行った変更
- Dart: `forge_runtime_state.dart`の未使用import削除、`ForgeStateStore({})`
  等8箇所以上への明示的型引数追加(自動検出スクリプトで発見)。
- Python: `backend/app/ai/runtime/prompt_pipeline.py`を新規実装(既存の
  `planner.py`/`critic.py`/`repair.py`/`context_builder.py`/
  `provider_router.py`と組み合わせ、PHASE9のフローを実現)。
- `backend/tests/test_ai_runtime.py`新規(21件、実行・全合格を確認)。
- `docs/spec/AI_RUNTIME.md`・`PROMPT_PIPELINE.md`・`NATIVE_AI_ROADMAP.md`新設。
- `TECH_DEBT.md`: 解消済み(Analyzer Warning)を明記、TD15〜TD17を追加。
- `docs/DECISIONS.md`: D44〜D47を追加。

## 変更理由
`backend/app/ai/runtime/`は既存の`backend/app/ai/foundation/`
(FORGE-MILESTONE-002)と概念的に重複するため、型の重複定義を避け
既存型をエイリアスとして再利用する方針を取った(D44)。
「AI実装したふり」を避けるため、実際に動作させたのは非AI的なロジック
(ProviderRouterのルーティング、PromptPipelineのオーケストレーション、
Validator呼び出し)のみに限定し、AI推論そのものは全てStub化した。
