# FORGE IR v1 — Architecture Proposal

**目的:** プラットフォーム非依存の中間表現を導入し、Forgeを
「Flutter用JSON生成AI」から「プラットフォーム非依存のアプリ記述基盤」へ進化させる
**種別:** 設計書のみ(実装は次フェーズ)
**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-18

**前提**: 本提案はForge Language v1.3 Architecture Proposal(前回提出)
の内容を包含・再配置する。v1.3で「Forge Languageに持たせる」と提案した
`record_schemas`/Field/Validationの概念は、本提案では**IR層へ移し、
Forge Languageはその「コンパイル先の1つ」という位置づけへ変わる**。
v1.3提案そのものが無駄になるわけではなく、v1.3の設計知見(特に
「Compilerが静的にしか値を合成できない」という制約、「Widget種類を
無闇に増やさない」という方針)はIR設計にもそのまま引き継ぐ。

---

## 0. Design Philosophy

1. **IRは「何をするアプリか」を表現し、「どう描画するか」は表現しない**。
   Entity(データ)・View(画面の意図)・Action(操作)・Event(結びつき)
   ・Navigation(画面遷移)という、**どのUIフレームワークでも共通して
   存在する概念**だけをIRの語彙にする。Widget名・state_ref・JSON構造
   といった、Forge Language(Flutter向け)固有の概念は一切含めない。
2. **IRは決定的に生成できる程度に十分具体的である**。抽象的すぎて
   「結局コンパイラ側で何でも解釈できてしまう」状態は避ける。IRは
   ルールベースのforge_aiが決定的に生成できる、有限で明確な語彙を持つ
   (Prompt→ApplicationPlanの生成が既に決定的であるのと同じ設計思想)。
3. **IRは複数のコンパイル先を平等に扱う**。「Flutterに一番都合が良い
   IR」ではなく、「Flutter/React/SwiftUI/Jetpack Composeのいずれもが
   妥当に解釈できるIR」を目指す。この判断基準として、**新しいIR要素を
   追加する際は、「これはFlutter以外のフレームワークでも同じ意味を
   持つか?」を必ず自問する**、という設計ガバナンスを明文化する
   (10章「デメリット」で述べる「IRがFlutter色に染まっていく」リスク
   への対策)。
4. **既存の資産(ApplicationPlan・Compiler)を破壊しない**。IRは
   ApplicationPlanとForge Languageの**間に挿入される新しい層**であり、
   既存の`Planner`・`DomainClassifier`・`PromptPipeline`の責務は
   一切変更しない(6章Migration Plan)。

---

## 1. FORGE IRとは何か

### 1.1 役割

FORGE IRは、`ApplicationPlan`(「何を作りたいか」という、まだ画面や
操作の詳細に踏み込んでいない計画)と、`Forge Language`(Flutter
Runtimeが実際に解釈できる具体的なJSON UI)との**間に立つ、プラット
フォーム非依存の設計図**である。

コンパイラ理論に例えるなら、`ApplicationPlan`が「ソースコード
(自然言語由来の意図)」、`Forge Language`が「特定CPU向けの機械語
(Flutter向けJSON)」だとすると、FORGE IRは**LLVM IRのような中間表現**
に相当する。1つのIRから、複数の「コード生成器(Compiler Backend)」が
異なるターゲット(Flutter/React/SwiftUI等)向けの出力を作れるように
する。

### 1.2 責務

- アプリが扱う**データの形**(Entity/Field/Relationship)を表現する。
- アプリの**画面の意図**(一覧を見せたい、入力を受け付けたい、詳細を
  見せたい)を表現する。ただし「どのWidgetで」「どんな配置で」までは
  踏み込まない。
- アプリの**振る舞い**(作成・更新・削除・画面遷移)を、抽象的な
  Actionとして表現する。
- **画面同士のつながり**(Event: 「この画面でこの操作をしたら、この
  Actionが起きる」、Navigation: 「その結果どの画面に移るか」)を
  表現する。
- Validationルールを、特定のUIフレームワークのバリデーション機構に
  依存しない形で表現する。

### 1.3 設計思想(まとめ)

IRは「意味(Semantics)の層」であり、Forge Languageは「表現
(Presentation)の層」である。この2つを分離することで、意味の生成
(自然言語理解・Domain推論・データモデル設計)と、表現の生成
(Widget選択・レイアウト・具体的なAction JSON)を、独立して開発・
テスト・拡張できるようにする。

---

## 2. IRが持つべき要素

検討した8要素(Entity/Field/Relationship/View/Action/Validation/
Event/Navigation)それぞれについて、**IRに含めるべきか、どこまで
含めるべきか**を個別に判断する。

| 要素 | IRに含めるか | 理由・粒度 |
|---|---|---|
| Entity | ○ 含める | データの型そのもの。プラットフォーム非依存の中核 |
| Field | ○ 含める | Entityの構成要素。型(string/number/boolean/date/choice)は含めるが、入力Widgetの種類(text_field等)は含めない |
| Relationship | △ 最小限含める | 現時点のDomain(FishRecord等)は単一Entityのみで関係を持たないため、**スキーマの骨組みだけ用意し、実データは今回生成しない**(9章で詳述) |
| View | ○ 含める。ただし「意図」レベルに留める | `list`/`form`/`detail`という3種の意図のみ。レイアウト(card/table等、v1.3で検討した`layout`プロパティ)は**IRに含めない**(Forge Language Compilerが決める) |
| Action | ○ 含める。ただし抽象操作のみ | `create_entity`/`update_entity`/`delete_entity`/`navigate`という4種。v1.3で設計した`composite`/`reset_state`等の「Forge Runtimeでの実現方法」はIRには一切現れない |
| Validation | ○ 含める | Field単位・Entity単位のルールは、"required"/"pattern"等の抽象的な語彙で表現でき、どのUIフレームワークでも意味が通じるため、そのままIRへ格上げする |
| Event | ○ 含める | ViewとActionを結びつける(「この画面のこの操作でこのActionが起きる」)。Forge LanguageのAction JSON(submit_action等)は、Eventの**具体的な実現方法の1つ**という位置づけになる |
| Navigation | ○ 含める(ただし理想形として) | 画面同士の遷移グラフ。**重要**: 現在のForge Language(Flutterの状態管理の制約、Template-aware Compiler Stage1で発見した「stateは画面ごとにスコープされる」制約)では、複数Viewを複数画面として実現できず、Forge Language Compilerが1画面へ「畳み込む」必要がある。**IR自体はこの制約を持たない**(3.3節で詳述) |

### 2.1 IRに含めないもの(明確化)

- Widget名(`text_field`/`checklist`/`card`等)
- state_ref等、特定の状態管理実装に紐づく識別子
- レイアウト・スタイル情報(色・余白・配置順序の細部)
- プラットフォーム固有のAction実装(`composite`/`add_item`等)

---

## 3. IRとForge Languageの責務分離

### 3.1 原則

**IRは「何が起きるべきか」を表現し、Forge Languageは「Flutter
Runtime上でそれをどう実現するか」を表現する。**

### 3.2 具体例で見る分離

IRのView(意図):

```
View(id="fish_list", kind="list", entity="FishRecord", display_fields=["species","size","weight","location"])
View(id="fish_form", kind="form", entity="FishRecord", mode="create")
Event(id="on_fish_form_submit", trigger="submit", source_view="fish_form", action="create_fish_record")
Action(id="create_fish_record", kind="create_entity", entity="FishRecord")
```

Forge Language Compilerが、このIRから実際に生成する内容(v1.3
Architecture Proposalで設計済みの語彙):

- `fish_list` → `checklist` Widget(現行)または`record_list_view`
  Widget(v1.3導入後)への変換。**どちらのWidgetを使うかは、Forge
  Language Compilerの実装が決める判断であり、IRはそこに関与しない**。
- `fish_form` → `form` + `text_field`群(現行の実装)、または
  `record_form`(v1.3)への変換。
- `create_fish_record` Action → v1.3で設計した`add_record`
  (または現行実装の`composite([add_item, reset_state...])`)への変換。

### 3.3 「画面をまたぐ制約」はForge Language側の問題として吸収する

Template-aware Compiler Stage1で発見した制約(Forge Languageの
stateは画面ごとにスコープされ、複数画面にまたがる状態共有ができない)
は、**Forge Language(および現行Flutter Runtime実装)固有の制約**
であり、IRの表現力を制限する理由にはしない。

IRの`fish_list`・`fish_form`は、理想的には**別々のView(≒別画面)**
として表現してよい。Forge Language Compilerは、このIRを実際の
Forge Language文書へ変換する際に、**現行の制約に合わせて1画面へ
畳み込む**(Stage1で実施した設計)という、**Forge Language Compiler
自身の実装判断**として処理する。将来、Forge Language側でこの制約が
解消されれば(例: 画面をまたぐ共有stateの導入)、IRを一切変更せずに、
Forge Language Compilerの出力だけがより自然な複数画面構成に変わる。
**これこそが、責務分離がもたらす具体的な利益である。**

---

## 4. IR Data Model

以下はデータ構造の設計案(実装はしない、設計としての型定義)。

```
ForgeIR
├── entities: tuple[Entity, ...]
├── views: tuple[View, ...]
├── actions: tuple[Action, ...]
├── events: tuple[Event, ...]
└── navigation: NavigationGraph

Entity
├── name: str                          例: "FishRecord"
├── fields: tuple[Field, ...]
└── entity_validations: tuple[EntityValidationRule, ...] = ()   (5章)

Field
├── name: str                          例: "species"
├── label: str                         例: "魚種"
├── type: FieldType                    string | number | boolean | date | choice | reference
├── required: bool
├── choices: tuple[str, ...] | None    type="choice"の場合のみ
└── validations: tuple[FieldValidationRule, ...] = ()

Relationship(骨組みのみ、9章)
├── from_entity: str
├── to_entity: str
└── kind: "has_many" | "belongs_to"

View
├── id: str
├── kind: ViewKind                     list | form | detail
├── entity: str                        対象Entity名
├── display_fields: tuple[str, ...] | None   list/detail用。Noneは全Field
└── mode: "create" | "edit" | None     form用

Action
├── id: str
├── kind: ActionKind                   create_entity | update_entity | delete_entity | navigate
├── entity: str | None
└── target_view: str | None            navigate用

Event
├── id: str
├── trigger: EventTrigger              submit | tap | (将来拡張)
├── source_view: str                   どのViewで発生するか
└── action: str                        Action.idへの参照

NavigationGraph
├── initial_view: str
└── edges: tuple[tuple[str, str], ...]  (from_view_id, to_view_id)。Eventのnavigate Actionから導出可能なため、保存は冗長キャッシュという位置づけでもよい

FieldValidationRule
├── type: "required" | "min" | "max" | "min_length" | "max_length" | "pattern"
├── value: Any
└── message: str

EntityValidationRule(5章、優先度低)
├── type: "field_comparison"
├── left: str / right: str (Field名)
├── operator: "lte" | "lt" | "gte" | "gt" | "eq" | "ne"
└── message: str
```

この構造は、v1.3提案の`record_schemas`/Field/Validationの語彙を
ほぼそのまま踏襲しているが、**「Forge Languageの文書内の1キー」
ではなく、「独立したPythonデータ構造(将来的にはJSON)」として** IR
専用モジュールへ切り出す(6章)。

---

## 5. Validation設計(IR層への格上げ)

v1.3提案の5章で設計したField単位・Entity単位のValidationは、
そのままIRの語彙として採用する。抽象的なルール("required"・
"pattern"・Field比較)は、Flutter固有ではなくどのUIフレームワークでも
同じ意味を持つため、IR層に置くことが自然である。

Entity単位のValidation(Field横断ルール)は、v1.3と同様に**優先度
低・任意拡張**として位置づける(9章リスクで詳述)。

---

## 6. IRとCompilerの関係、Migration Plan

### 6.1 新しいパイプライン構成

```
Prompt
  ↓ (既存、無変更)
ApplicationPlan            <- forge_ai.core.planner.Planner
  ↓ (新規)
FORGE IR                   <- forge_ai.core.ir.IRGenerator  [新設]
  ↓ (既存Compilerを改名・入力型変更)
ForgeDocument               <- forge_ai.core.compiler.ForgeLanguageCompiler  [Compilerから改名]
  ↓ (既存、無変更)
Flutter Runtime
```

### 6.2 各層の対応表(既存コードとの関係)

| 新設・変更 | 既存との関係 |
|---|---|
| `forge_ai/core/ir/ir_types.py`(新設) | `ForgeIR`/`Entity`/`Field`等のdataclass定義。新規モジュール、既存への依存なし |
| `forge_ai/core/ir/ir_generator.py`(新設) | **Template-aware Compiler Stage1で`compiler.py`に置いた`DomainField`/`DomainDataModel`/`_DOMAIN_DATA_MODELS`をここへ移設する**。これらは元々「Entityの定義」そのものであり、IR層に属するべきものだった、という認識の修正でもある |
| `forge_ai/core/compiler.py`(変更) | `Compiler.compile(plan, domain_category)`という入力を、`ForgeLanguageCompiler.compile(ir: ForgeIR)`という入力へ変更する。**Widget選択・Action JSON生成のロジック自体は、Stage1で書いたものをほぼそのまま使える**(入力元がApplicationPlanの一部からForgeIRのEntity/View/Actionへ変わるだけで、「魚種→text_field」のような変換ロジック自体の実装難易度は上がらない) |
| `forge_ai/core/orchestration/pipeline_orchestrator.py`(最小変更) | Compiler呼び出し箇所(1行)を、`ir = ir_generator.generate(context.plan, domain_category); forge_document = forge_language_compiler.compile(ir)`という2行へ変更する。Stage1導入時と同じ規模の変更に収まる |

### 6.3 段階的Migration Plan

**Phase 1: IR型定義のみ導入(無リスク)**
- `forge_ai/core/ir/ir_types.py`を新設。既存コードへの参照・依存は
  無いため、既存テスト・既存の動作に一切影響しない。

**Phase 2: IR Generatorを、Stage1の3 Domainだけに適用**
- `fishing_log`/`household_budget`/`habit_tracking`について、
  `ApplicationPlan`(+domain_category)からForgeIRを生成する
  `IRGenerator`を実装する。
- `ForgeLanguageCompiler`(現行`compiler.py`の`_compile_record_
  template`ロジックを移植)が、このForgeIRを消費してForgeDocumentを
  生成する。
- **他のDomain(shopping等)は、既存の`Compiler.compile(plan,
  domain_category=None)`パス(Checklist単一画面)をそのまま使い続ける**
  (Stage1と同じ「段階的移行」パターンの再利用)。

**Phase 3: 既存Checklist Domainも、簡易IR経由へ寄せる(任意・将来)**
- 既存6 Domainについても、「単一Fieldを持つEntity」という最小限のIR
  へ変換してから、`ForgeLanguageCompiler`がChecklist Widgetへ変換する
  形に統一する。これにより、Compiler内の「IR未経由の分岐」が無くなり、
  コードベースが単純化する。**この段階は、Phase2が安定してから着手する
  ことを推奨する**(急ぐ理由が無いため)。

**Phase 4(将来、Flutter以外への展開)**
- `forge_ai/core/compiler_backends/react_compiler.py`のような、
  新しい「コンパイル先」を追加する。**この段階になって初めて、IRの
  抽象化が本当に十分だったかを実証できる**(9章)。

---

## 7. 将来性: Flutter以外への展開

### 7.1 新しいターゲットの追加パターン

React/SwiftUI/Jetpack Compose/Web/Desktopいずれについても、追加手順は
同じパターンになる。

1. そのターゲット向けの「Compiler Backend」を1つ新設する
   (`ForgeLanguageCompiler`と対等な、`ForgeIR`を入力に取るクラス)。
2. IRのView種別(list/form/detail)を、そのフレームワークの慣用的な
   コンポーネントへ対応付ける(例: React backendなら`list`→
   テーブルコンポーネントやカードのリスト、SwiftUI backendなら
   `List` + `NavigationLink`等)。
3. IRのAction種別(create_entity等)を、そのフレームワークの状態管理
   慣用パターン(ReactならuseState/Redux、SwiftUIなら
   `@State`/`@ObservedObject`等)へ対応付ける。
4. **`PromptPipeline`・`DomainClassifier`・`Planner`・`IRGenerator`は
   一切変更しない**。新ターゲット追加のコストは、Compiler Backend
   1つ分に閉じる。

### 7.2 具体的に何が「再利用」されるのか

- 自然言語理解(Intent抽出・Ambiguity Detection・Domain分類)
- Entity/Field設計(IRGeneratorが持つ`_DOMAIN_DATA_MODELS`相当のデータ)
- Validation ルール
- 画面遷移グラフの設計判断

これらは全て**アプリの「意味」に属する判断であり、どの画面フレーム
ワークで実現するかとは独立**である。この独立性こそが、複数プラット
フォーム展開時の最大の資産になる。

### 7.3 現実的な留保

Web/Desktop/SwiftUI/Jetpack Composeは、それぞれ固有のUI慣用句・
ナビゲーションパターン・状態管理の作法を持つ。IRが「共通項」だけを
抽出している以上、**各Compiler Backendには、そのフレームワーム
固有の“良いUXにする”ための判断が一定量残る**(IRを作ればUI生成が
自動化されて0になる、という誤解は避けるべきである)。IRが担うのは
「意味の一貫性の保証」であり、「各プラットフォームでの質の高いUI
生成」は各Backend自身の責務として残り続ける。

---

## 8. メリット

1. **新ターゲット追加のコストが、Compiler Backend1つ分に限定される**
   (7章)。
2. **Forge Language自体の進化(v1.3のRecord対応等)が、IR層より上の
   コード(Planner・DomainClassifier等)に影響しない**。Forge Language
   がv1.4・v1.5と進化しても、IRとIR Generatorは無変更でよい可能性が
   高い。
3. **テスト容易性の向上**。IRは単なるデータ構造であり、「この入力
   文からこのIRが生成されるべきだ」というテストと、「このIRから
   このForgeDocumentが生成されるべきだ」というテストを、完全に独立
   させられる(現在は1つのCompilerテストで両方を混ぜて検証している)。
4. **Stage1で発見した「Forge Language固有の制約」(画面をまたぐ
   state共有不可等)を、IRの設計を汚さずに切り離せる**(3.3節)。

## 9. デメリット

1. **層が1つ増えることによる複雑さの増加**。現在は
   `Compiler.compile(plan, domain_category)`という1メソッド呼び出し
   で完結していたものが、`IRGenerator.generate()` →
   `ForgeLanguageCompiler.compile()`という2段階になる。プロジェクトの
   現在の規模(単一ターゲットのみ)を考えると、**このコストは今すぐ
   全面的に回収できるものではない**(10章リスク1)。
2. **IRの抽象化が本当に妥当かどうかは、2つ目のターゲットを実際に
   作るまで実証できない**。今回の設計はFlutterという唯一の実例から
   帰納的に抽象化したものであり、React等を実際に実装する段階で、
   IRの語彙が不足していたり、逆にFlutter色が抜けきっていなかったり
   することが判明する可能性がある。
3. **Relationship(Entity間の関係)は、現時点で実データが無いまま
   スキーマだけ用意することになる**。使われない設計要素を持つことは、
   将来の変更コストを増やすリスクがある(2章)。

## 10. リスク

1. **YAGNI(過剰な先行設計)リスク**: 現在Forgeが対象とするプラット
   フォームはFlutterのみである。「将来使うかもしれない機能の先行
   実装」という既存の禁止事項に、IR層の導入そのものが抵触しないか、
   慎重な判断が必要。**今回はCEOから明示的にプラットフォーム展開を
   見据えた指示があるため、この禁止事項の例外として扱うのが妥当と
   判断する**が、実装フェーズでは、6.3節Phase1〜2という**最小限の
   範囲(Stage1の3 Domainのみ)にまず限定し、Phase3以降は需要が
   実証されてから着手する**ことを強く推奨する。
2. **IRのガバナンス崩壊リスク**: 開発が進むにつれ、「Flutter向けに
   都合が良いから」という理由でIRへFlutter固有の概念が忍び込む
   誘惑が常にある。0章4項の自問(「これはFlutter以外でも同じ意味を
   持つか?」)を、コードレビューのチェック項目として明文化することを
   提案する。
3. **既存254件超のテストへの影響**: 6.3節Phase2の範囲(Stage1の3
   Domainのみ)であれば、既存Checklist系のテストには一切触れないため
   リスクは低い。Phase3(既存Domainの IR経由への統一)まで進める場合、
   既存Golden Testの期待値が変わらないことの追加検証が必要になる。

---

## 11. 実装順序(推奨)

1. `forge_ai/core/ir/ir_types.py`: `ForgeIR`等のdataclass定義のみ
   (6.3節Phase1)。
2. `forge_ai/core/ir/ir_generator.py`: Stage1の3 Domain分の
   `IRGenerator`実装(`DomainDataModel`等をcompiler.pyから移設)。
3. `ForgeLanguageCompiler`: 現行`_compile_record_template()`の
   ロジックを、`ForgeIR`入力へ書き換える形で移植。
4. `pipeline_orchestrator.py`の呼び出し箇所を2行に変更(Stage1の
   3 Domainのみ、他は現行のまま)。
5. IR単体のテスト(「この入力からこのIRが生成される」)と、Forge
   Language Compiler単体のテスト(「このIRからこのForgeDocumentが
   生成される」)を分離して整備する。
6. (この時点でPhase2完了。実運用しながら、Phase3・Phase4の要否を
   判断する)。

---

## 12. 将来の拡張性(まとめ)

FORGE IRの導入により、Forgeは以下の性質を獲得する。

- **意味の生成(自然言語理解・Domain推論・データモデル設計)と、
  表現の生成(UI・状態管理・操作の具体実装)が独立して進化できる**。
- **新しいUIフレームワークへの対応は、既存資産(Prompt理解〜IR生成)
  を一切変更せず、新しいCompiler Backend 1つを追加するだけで実現
  できる、という設計上の保証**が得られる。
- 一方で、この保証は「IRの語彙が本当にプラットフォーム非依存であり
  続けているか」という継続的なガバナンスに支えられており、一度設計
  すれば自動的に維持されるものではない、という点を明記して本提案の
  結びとする。
