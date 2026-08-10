# Prompt Pipeline(backend/app/ai/runtime/prompt_pipeline.py）

PHASE9で要求されたフローを、Protocol実装(既定はStub)を注入して実行する
薄いオーケストレーション層。**このクラス自身にAI推論ロジックは無い。**

---

## 1. フロー全体

```
Natural Language
    │  AIPlanner.interpret()
    ▼
Intent(=IntentIR)
    │  AIPlanner.plan()
    ▼
Plan(=PlanIR)
    │  LanguageGenerator.generate()  ※foundation/interfaces.pyの既存Protocol
    ▼
JSON(draft_document)
    │  schema_validator.validate_forge_document()  ※実際に動作する既存Validator
    ▼
ValidationResult
    ├─ 合格 ──────────────────────────────┐
    │                                        ▼
    │                                  AICritic.evaluate()
    │                                        │
    └─ 不合格                                ▼
         │  AIRepair.repair()          CriticResult
         │  (最大 MAX_REPAIR_ATTEMPTS 回)
         ▼
    再度 validate_forge_document()
         │
    (合格するかattempt上限に達するまで繰り返す)
```

## 2. 各段階の実行方式

| 段階 | 実装状況 |
|---|---|
| Planner (Intent/Plan) | Stub(`NotImplementedError`) |
| Language Generator (Plan→JSON) | Stub(`NotImplementedError`) |
| **Validator** | **実際に動作する**(`schema_validator.validate_forge_document`、既存188件のテストで検証済み) |
| Repair | Stub(`NotImplementedError`) |
| Critic | Stub(`NotImplementedError`) |

Validatorだけが実際に動作する、という非対称性は意図的である。Validatorは
FORGE-MILESTONE-002/003で既に確定・凍結された、決定的なコードだからである。
AI推論を要する4段階(Planner/LanguageGenerator/Repair/Critic)だけが
「今回はStub」の対象になる。

## 3. Repair Loopの安全設計

共通指示書6.5節「修正回数には上限を設ける。推奨は最大2回。無限修正
ループは禁止」に従い、`MAX_REPAIR_ATTEMPTS = 2`を既定値とした。
`PromptPipeline.__init__`で`max_repair_attempts`を上書きできる
(テストでは1回に制限したケースも検証済み)。

ループの終了条件は「合格した」または「試行回数の上限に達した」の
いずれかであり、これ以外の条件でループを継続しない
(`test_pipeline_invalid_document_triggers_repair_up_to_max_attempts`で
回帰確認済み)。

## 4. なぜ「実装したふり」にならないか

`PromptPipeline.run()`は、注入されたPlanner/LanguageGenerator/Critic/
Repairのいずれかが`StubXxx`であれば、その段階の呼び出し時点で
`NotImplementedError`を送出し、それを`try/except`で握り潰さずに
呼び出し元へ伝播させる(`test_pipeline_with_all_stubs_raises_on_first_call`
で確認済み)。「パイプラインが最後まで動いた」という結果を、実際には
一度も実LLMを呼んでいないのに作り出すことは無い。

## 5. テストにおけるテストダブルについて

`tests/test_ai_runtime.py`では、Stub以外に`_FakePlanner`等の
テストダブルを使っている。これらは「AIの実装」ではなく、**Pipelineの
オーケストレーションロジック(分岐・ループ・記録)が正しいかどうかを
検証するための決定的なテスト専用コード**であり、本番のPromptPipelineの
デフォルト実装として使われることは無い(`app/ai/runtime/`配下の
本体コードには一切登場しない、`tests/`配下限定のコード)。
