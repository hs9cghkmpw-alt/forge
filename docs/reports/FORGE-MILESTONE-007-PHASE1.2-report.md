# FORGE-MILESTONE-007 Phase 1.2 実施レポート — Meaning Model導入

**Ref:** M007 Phase 1 Minimal Cognitive Slice(Phase 1.2、Meaning Model導入)
**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-16

Meaning ModelをCognitive Pipelineへ正式接続し、複雑な修飾条件を含む
6入力の意味を構造化して、Requirement Extraction・Application Planning・
Decision Traceへ実際に反映した。複数画面化・新規Domainには進んでいない。

---

## 1. 変更ファイル一覧

```
forge_ai/core/orchestration/cognitive_types.py       — SemanticUnit/ExtractedMeaning(Cognitive版)・Requirement.derived_from追加
forge_ai/contracts/cognitive_interfaces.py             — CognitiveMeaningExtractorProtocol新設、RequirementExtractorProtocolを3引数へ復元
forge_ai/core/orchestration/cognitive_context.py         — CognitiveContext.meaningフィールド追加
forge_ai/core/orchestration/cognitive_dependencies.py     — meaning_extractor追加
forge_ai/core/orchestration/outcomes.py                    — Success構築の必須フィールドにmeaningを追加
forge_ai/core/orchestration/pipeline_orchestrator.py         — Meaning Model段階を正式接続、Decision Trace追加
forge_ai/core/understanding/meaning_extractor.py               — 新規、CognitiveMeaningExtractor実装
forge_ai/core/understanding/requirement_extractor.py             — meaning, world, intentの3引数へ復元、Meaning由来Requirement生成
forge_ai/core/planning/application_planner.py                     — Meaning由来requirementのdata_entities/required_actionsへの反映
forge_ai/core/critic/design_critic.py                                — intent_meaning_fidelity軸を追加
forge_ai/core/pipeline.py                                              — meaning_extractor配線
forge_ai/tests/test_understanding.py                                    — Meaning Extractor Unit Test・Requirement変換Test追加
forge_ai/tests/test_cognitive_orchestrator_integration.py                 — Meaning Model Integration Test追加
forge_ai/tests/test_cognitive_pipeline_complex_golden.py（新規）             — 複雑入力6例のGolden Test
forge_ai/tests/golden_cognitive_complex/*.json（新規、6件）                   — Golden Test用の凍結データ
```

---

## 2. 実装したMeaning型と抽出規則

### 2.1 データ型(Cognitive専用、Legacy`meaning_model.py`とは別型)

```python
@dataclass(frozen=True)
class SemanticUnit:
    subject: str | None
    action: str
    target: str | None
    qualifiers: tuple[str, ...] = ()
    evidence: str = ""

@dataclass(frozen=True)
class ExtractedMeaning:
    summary: str
    semantic_units: tuple[SemanticUnit, ...] = ()
    actors: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    preferences: tuple[str, ...] = ()
    temporal_conditions: tuple[str, ...] = ()
    state_conditions: tuple[str, ...] = ()
    evidence_spans: tuple[str, ...] = ()
    confidence: float = 1.0
```

Legacy`meaning_model.py`の`ExtractedMeaning`(`raw_text`必須の4フィールド)
とは意図的に別クラスとした(既存の`raw_text: str`と新規の`summary: str`が
共に必須の第1フィールドとなり、単純な拡張では不自然な型になるため。
Legacy/Cognitive Protocol分離の原則に倣った)。

### 2.2 抽出規則(決定的なキーワード辞書、実LLM非依存)

Intent Recognizer・Domain Classifierと同じ手法で、日本語キーワード→
意味カテゴリの対応表を用意した。

| カテゴリ | 例 |
|---|---|
| Actor | "家族"→家族、"友人"→友人 |
| Action | "共有"→share、"記録"→record、"設定"→set、"確認"→view |
| Constraint | "共有"→複数利用者による共有アクセスが必要 |
| Preference | "写真"→写真の添付を希望、"気分"→気分の記録を希望 |
| Temporal | "毎週月曜日"→毎週月曜日、"回答後"→回答後、"期限"→期限あり |
| State | "少なくなったら"→在庫が少ない状態、"優先度"→優先度による状態区分 |

---

## 3. 6つの複雑入力の実行結果

| 入力 | Domain | Template | Actor | Entity(追加分) | Action | Constraint/Temporal/State | release_ready |
|---|---|---|---|---|---|---|---|
| 家族で共有できる買い物リストを作りたい | shopping | checklist | 家族 | — | share | 複数利用者による共有アクセスが必要 | True |
| 写真と気分を記録できる日記がほしい | diary | memo | — | photo, mood | record | — | True |
| 期限と優先度を設定できるタスク管理アプリ | task_management | checklist | — | — | set, manage | 期限あり(temporal) / 優先度による状態区分(state) | True |
| 在庫が少なくなったら分かるようにしたい | inventory | tracker | — | — | notify | 在庫が少ない状態(state) | True |
| 回答後に結果を一覧で確認できるアンケート | survey | form | — | — | view, list_view | 回答後(temporal) | True |
| 毎週月曜日の予定を管理したい | schedule | calendar | — | — | manage | 毎週月曜日(temporal) | True |

既存6例(単純入力)も、全てDomain/Template判定を変えずSUCCESSへ到達する
ことを確認した。

---

## 4. Meaning → Requirement → Planの具体的な伝播例

「家族で共有できる買い物リストを作りたい」の例:

```
Meaning: actors=('家族',), actions=('share',), constraints=('複数利用者による共有アクセスが必要',)
  ↓
Requirement: category=permission, operation_ref='share', mandatory=True,
             derived_from='meaning', rationale='Meaning.actors/actions(共有)に基づく'
Requirement: category=validation, description='制約: 複数利用者による共有アクセスが必要',
             derived_from='meaning'
  ↓
ApplicationPlan: required_actions=(..., 'share')  ← 実際に反映
                 validation_rules に制約の説明を含む  ← 実際に反映
unassigned_requirements: (Accessibility要件のみ、非mandatory)
```

`derived_from`(既定値`"world"`、Meaning由来は`"meaning"`)という新
フィールドを追加し、ApplicationPlannerが「World由来の基本要件」と
「Meaning由来の追加要件」を区別できるようにした。**Meaning由来の
mandatory要件のtarget_ref/operation_refのみ**を自動的にdata_entities/
required_actionsへ反映する(実際にテストして発見: 区別なしに全ての
mandatory要件を自動反映すると、Phase 1.1で検証した「Planへ実際に
反映されていない要件はunassignedのままになる」という機械判定機能
そのものが無意味になってしまう問題があったため)。

---

## 5. Meaning Fidelity Criticの評価例

`design_critic.py`に`intent_meaning_fidelity`軸を追加した(8軸目)。
Meaning由来(`derived_from == "meaning"`)のmandatory要件が未割当の
場合、blocking issueにする。実際に、target_ref/operation_refを持たない
架空のカテゴリでMeaning由来のmandatory要件を作るテスト
(`test_mandatory_meaning_requirement_unassigned_blocks_critic`)で、
`CognitivePipelineNeedsConfirmation`へ正しく到達することを確認した。

---

## 6. Decision Traceの実例

「家族で共有できる買い物リストを作りたい」の`meaning_extraction`段階:

```
[meaning_extraction]
  decision: actors=('家族',), entities=('item', 'price', 'quantity', 'store'), actions=('share',)
  reason: constraints=('複数利用者による共有アクセスが必要',), temporal=(), state=(),
    evidence_spans=('家族', '共有'), rule=keyword_pattern_dictionary_v1
  confidence: 0.9
```

`meaning_extraction`は`domain_classification`の後、
`preliminary_template_selection`(実質的にRequirement Extractionの後)の
前に記録されており、パイプライン順序(World→Meaning→Requirement)を
Decision Trace自体からも確認できる。

---

## 7. Forge AI全テスト結果

```
$ python -m unittest discover -s forge_ai/tests -p "test_*.py"
Ran 192 tests in 0.065s
OK
```
既存164件を維持し、新規28件(Unit 18件・Integration 6件・Golden 4件)を
追加した。

## 8. Backend全テスト結果

```
$ python -m unittest discover -s backend/tests -p "test_*.py"
Ran 265 tests in 0.025s
OK (skipped=17)
```
前回セッションから件数・結果とも無変化。

---

## 9. 未実装・既知の制限(正直な申告)

- **キーワード辞書の網羅性**: 今回のキーワード辞書は、CEO指定の12入力
  (単純6+複雑6)を中心に構築しており、これら以外の自然言語表現
  (同義語・言い換え)には対応できない可能性が高い。
- **Domain/Genericの重複(既知、Phase 1から継続)**: GenericDomainの
  "item"概念とShopping Domainの"item"概念が同名であるため、
  「買い物リストを作りたい」でscore_marginが0になる(既知の軽微な
  quirk、動作結果自体は正しい)。
- **semantic_unitsの単純さ**: 各actionごとに1つのSemanticUnitを
  生成するが、subjectは「最初に検出されたactor」を機械的に割り当てる
  簡易的な実装であり、複数actor・複数actionの正確な対応関係
  (誰が何をするか)までは表現できない。
- **`intent_meaning_fidelity`は8軸中1軸のみ**: M006 14章のIntent
  Fidelityが本来求める、より広い評価(Domain/World/Requirementとの
  総合的な整合性)ではなく、「Meaning由来mandatory要件の未割当検出」
  という限定的な実装である。

---

## 10. 複数画面化へ進める状態かどうかの判断

**Meaning Model導入という観点では、次段階(複数画面化)へ進める状態と
判断する。** 根拠: (1) 12入力全てが実際に成功し、Meaning由来の情報が
Decision Traceだけでなく実際のPlanへ反映されることを確認した。
(2) Meaning Fidelity Criticにより、未反映のmandatory情報を検出できる
安全機構が機能している。(3) 既存192件(forge_ai)・265件(backend)の
回帰が無い。

ただし、現状は常に単一画面であるため、複数画面化の際は「どの画面へ
どの情報を割り当てるか」という新たな判断が必要になり、今回の
`derived_from`ベースの単純な割当ロジックの拡張(画面ごとの割当追跡)が
必要になる見込みである。
