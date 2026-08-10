# CHANGELOG (forge_ai)

## v0.1.0 — Initial Implementation (2026-07-12)

Project: Forge AI v0.1、キックオフ指示書「FORGE PROJECT — AI実装チーム
キックオフ指示書」に基づく初回実装。

### 追加

- `core/domain_model.py` — `Domain`/`DomainCategory`/`DomainConcept`/
  `DomainRegistry`。Shopping/Hospital/Attendance/Diary/Inventory/Genericの
  6カテゴリを定義。
- `core/world_model.py` — `Actor`/`WorldObject`/`Relationship`/`Rule`/`World`/
  `WorldModelBuilder`。
- `core/meaning_model.py` — `ExtractedMeaning`/`MeaningExtractor`。
- `core/intent_model.py` — `Intent`/`IntentBuilder`。
- `core/planner.py` — `ScreenPlan`/`ApplicationPlan`/`Planner`
  (Runtime非依存であることを回帰テストで保証)。
- `core/compiler.py` — `ForgeIRWidget`/`ForgeIRStateValue`/`ForgeIRScreen`/
  `ForgeIRDocument`/`Compiler`。Forge Language v1.0互換のJSONを生成。
- `core/pipeline.py` — `run_pipeline()`(薄いオーケストレーション関数)。
- `repair/repair_engine.py` — `RepairIssue`/`RepairResult`/`RepairEngine`
  (最大2イテレーション、無限リトライ無し)。
- `quality/quality_engine.py` — `QualityScore`/`QualityEngine`
  (Correctness/Completeness/Simplicity/Runtime Safety/Explainability/
  Maintainabilityの6軸)。
- `provider/provider_interface.py` — `AIProvider` Protocol/`ProviderResponse`。
- `provider/mock_provider.py` — `MockProvider`(決定的、実LLM非依存)。
- `prompt/prompt_builder.py` — `Prompt`/`PromptBuilder`
  (文字列連結を使わない構造化Prompt生成)。
- `contracts/interfaces.py` — 8つのProtocol定義(Interface First)。
- `tests/` — 80件のUnit Test(Mockのみで全実行可能、実行確認済み)。
- `docs/DESIGN_DECISIONS.md` — 実装前後の設計判断記録(D1〜D5)。
- `docs/KNOWN_LIMITATIONS.md` — 既知の制限5件。

### 実装中に発見した設計変更

- `__init__.py`をforge_ai/および全サブパッケージへ追加
  (`docs/DESIGN_DECISIONS.md` D5参照。一部の`unittest discover`起動方法で
  namespace packageがimportできない実際の問題を発見したため)。

### 今回実装しなかったもの(意図的、キックオフ指示書8章の禁止事項)

Claude/OpenAI/Gemini API、Ollama、MCP、Runtime接続、Flutter変更、
Database/Supabase接続、Tool Calling、Memory。
