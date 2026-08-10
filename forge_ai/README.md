# forge_ai — Forge Cognitive Engine (v0.1)

Forgeの最終目標である

```
自然言語 → 世界理解 → 意味理解 → 意図理解 → 設計 → Forge IR(JSON) → Runtime
```

のうち、**世界理解〜設計まで**(Domain → World → Meaning → Intent → Planner →
Compiler)を実装したパッケージ。

## これは何か / 何でないか

- **これは**: 自然言語を、検証可能なForge IR(将来Forge Language JSONへ
  シリアライズできる中間表現)へ変換するための、LLM非依存のCognitive Engine基盤。
- **これではない**: 「AIアプリ」ではない。ChatベースのAIアシスタントではなく、
  Software Design Engineである(キックオフ指示書1章)。
- **今回接続していないもの**: Claude/OpenAI/Gemini等の実LLM API、Flutter Runtime、
  Backend API、Supabase、Tool Calling、Memory(禁止事項8章)。

## クイックスタート

```bash
# forgeリポジトリのルートから
cd forge_ai
pip install -e .   # setup.py/pyproject.tomlは今回同梱していない。単体では
                    # `python -c "import sys; sys.path.insert(0, '..'); ..."` の
                    # ようにforgeリポジトリルートをsys.pathへ加えて使う想定。

# 最も簡単な実行例(forgeリポジトリルートで)
python3 -c "
from forge_ai.core.pipeline import run_pipeline
from forge_ai.provider.mock_provider import MockProvider

result = run_pipeline('add item track price', MockProvider())
print(result.plan.title)
print(result.ir.to_json_dict())
print(result.quality.to_dict())
"
```

## パイプライン全体図

```
自然言語(user_text)
    │
    ▼
DomainRegistry.resolve_from_keywords()  ─── core/domain_model.py
    │  (Domain: Shopping/Hospital/Attendance/Diary/Inventory/Generic)
    ▼
WorldModelBuilder.build()               ─── core/world_model.py
    │  (World: Actor/Object/Relationship/Rule。UIを知らない)
    ▼
MeaningExtractor.extract()              ─── core/meaning_model.py
    │  (ExtractedMeaning。Providerへ委譲。Worldは読み取り専用)
    ▼
IntentBuilder.build()                   ─── core/intent_model.py
    │  (Intent: goal/required_concepts/required_actions/constraints)
    ▼
Planner.plan()                          ─── core/planner.py
    │  (ApplicationPlan。Widget種別を一切含まない、Runtime非依存の設計)
    ▼
Compiler.compile()                      ─── core/compiler.py
    │  (ForgeIRDocument。Forge Widget/Action/State語彙のみを使う)
    ▼
[ここから先、Validator接続後]
RepairEngine.repair()                   ─── repair/repair_engine.py
QualityEngine.evaluate()                ─── quality/quality_engine.py
    │
    ▼
Forge Runtime(今回のスコープ外)
```

`core/pipeline.py`の`run_pipeline()`が、Domain解決からQuality評価までを
一括で実行する薄いオーケストレーション関数を提供する(状態を持つ
「巨大Manager」ではなく、単なる呼び出し順序の関数)。

## ディレクトリ構成

```
forge_ai/
├── core/
│   ├── domain_model.py     Domain定義(UIを知らない)
│   ├── world_model.py      Domain → World(Actor/Object/Relationship/Rule)
│   ├── meaning_model.py    自然文 → ExtractedMeaning(Worldは読み取り専用)
│   ├── intent_model.py     ExtractedMeaning → Intent
│   ├── planner.py          Intent → ApplicationPlan(Runtimeを知らない)
│   ├── compiler.py         ApplicationPlan → ForgeIRDocument
│   └── pipeline.py         上記を一括実行する薄い関数
├── repair/
│   └── repair_engine.py    ForgeIRDocument + issues → 修正済みIR
├── quality/
│   └── quality_engine.py   ForgeIRDocument → 6軸QualityScore
├── provider/
│   ├── provider_interface.py   AIProvider Protocol(LLM非依存の抽象契約)
│   └── mock_provider.py        決定的なMock実装(唯一の同梱Provider)
├── prompt/
│   └── prompt_builder.py   Prompt(構造化データ)を組み立てる唯一の入口
├── contracts/
│   └── interfaces.py       各段階のProtocol定義(Interface First)
├── tests/                  80件、Mockのみで全実行可能
└── docs/                   設計判断の詳細記録
```

## 設計原則

1. **Provider Independence**: どのモジュールも`AIProvider`という
   Protocolにのみ依存し、具体的な実装(Mock含む)のクラス名を知らない。
2. **PlannerはRuntimeを知らない**: `ApplicationPlan`/`ScreenPlan`には
   Forge Widget種別(text/button/checklist等)が一切登場しない
   (回帰テスト: `tests/test_planner.py`)。
3. **DomainはUIを知らない**: `Domain`/`DomainConcept`にWidget・画面という
   語彙は登場しない。
4. **Promptは文字列連結禁止**: `Prompt`はsystem/instruction/contextに
   分離された構造化データ。
5. **Repair Engineは無限リトライしない**: `max_iterations`(既定2)を超えて
   繰り返さない。1回のイテレーションで1件も直せなければ即座に打ち切る。
6. **未知の入力でクラッシュしない**: 空文字列・未知のDomainキーワード・
   未知の修正カテゴリ・不正なRepairIssue、いずれも例外を投げず、
   安全なフォールバック値を返す(`tests/`の`*_without_crashing`系テストで
   全モジュール回帰確認済み)。

## テストの実行方法

```bash
# forgeリポジトリのルートから(重要: forge_ai/の1つ上のディレクトリから実行する)
cd forge   # forge_aiの親ディレクトリ
python3 -m unittest discover -s forge_ai/tests -p "test_*.py"
```

80件、Mock Providerのみで全件実行・全件PASSする(実測済み。
`IMPLEMENTATION_REPORT.md`参照)。`backend/app/`が同じ環境に存在する場合、
1件だけ追加で実際のForge Language Validatorに対する外部検証も走るが、
これは任意(forge_ai/自体の必須テストではない)。

## 既知の制限

`docs/KNOWN_LIMITATIONS.md`を参照。特にMockProviderの日本語トークナイズは
単純な空白区切りであり、分かち書きされていない日本語文の意味的な分解は
行わない(実LLM接続後に解消される想定)。
