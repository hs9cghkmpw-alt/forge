# FORGE-PRODUCT-VISION-002: Conversational Problem-to-Tool Architecture

2026-08-11。CEO指示書「『アプリを作るAI』から『困りごとを話すと道具が
生まれるAI』への製品思想更新」への対応。Phase A〜D(監査・設計)を
このドキュメントにまとめる。Phase E(実装)は
`docs/reports/FORGE-PRODUCT-VISION-002-report.md`に記録する。

Forgeの一文定義(指示書30章、迷ったらここへ戻る):

> Forgeは、ユーザーにアプリを設計させるサービスではない。ユーザーが
> 日常の困りごとを自然に話すと、Forgeが問題を理解し、必要最小限の
> 道具を考え、使える状態で差し出し、その後も会話しながら一緒に
> 育てていくシステムである。

---

## Phase A. 現状監査 — 新Product Visionとの差分

現物(コード)を実際に読んで確認した事実のみを書く(推測・願望は
書かない)。

### A.1. 「Space / Forming / Held」という語彙は存在しない

`docs/`・`forge_ai/docs/`・`TECH_DEBT.md`・`CHANGELOG.md`を含む全リポジトリを
検索したが、"Space"/"Forming"/"Held"という製品概念は**どこにも存在しない**
(一致したのは`workspace`という無関係な単語のみ)。これは既存概念の
リネームではなく、**新規に導入する製品レイヤー**である。

### A.2. 現在のUXは「質問攻めにしない」原則に反する構造ではないが、「会話」でもない

現在のフロー(`frontend/lib/features/app_generation/presentation/screens/`
のHome→(Confirm相当)→Generating→Tool)は、指示書5章が禁止する「対象
ユーザーは？必要機能は？画面数は？色は？」のような**逐次質問リスト**には
なっていない(このプロジェクト自身が数セッション前にInspiration
Cards・単発自然文入力の形へ整理済み)。

しかし、指示書2章が理想とする「日常会話から自然に要件が浮かび上がる」
体験にも達していない。現状は:

1. ユーザーが1つの自然文を入力する(Home画面)。
2. Backend(`backend/app/ai/runtime/prompt_pipeline.py`)が
   `run_cognitive_pipeline()`を1回呼ぶ。
3. 曖昧・低confidenceな場合、**最大3往復**(`confirmation_store.py`
   `MAX_CONFIRMATION_ROUNDS = 3`)の一問一答が発生しうる
   (`POST /api/v1/ai/generate/confirm`)。
4. 十分な情報が揃ったと判定されると、その場でアプリ全体を生成する。

つまり「ASK」に相当する仕組み(`needs_confirmation`)は**既に存在する**。
指示書が要求する新規性は、(a) この仕組みを「エラー処理の脇道」ではなく
「体験の中心」として扱うこと、(b) 質問をLLMの曖昧さ検出任せにするのでは
なく、構造化されたNeed Model上のKnown/Unknown/Assumptionという明示的な
契約に基づいて選ぶこと、(c) 生成後も同じ会話から「育てる」(UPDATE)が
できること、の3点である。詳細はA.4・A.5参照。

### A.3. Confidenceの計算基盤は既にかなり成熟している

`forge_ai/core/orchestration/confidence.py`(ADR-007)が、指示書11章
「単純なLLM自己申告の0.86を信用してはいけない」と全く同じ思想で、
既に以下を実装済み:

* `compute_overall_confidence()`: `intent_confidence`・`domain_confidence`
  という決定的信号からConfidenceを組み立てる(LLMの自己申告ではなく、
  「抽出できた概念数」「Domain分類のスコア差」等の決定的な情報から
  計算する)。
* `classify_risk()`: `multiple_signals_low` / `intent_confidence_only_low`
  / `medium_band` / `high_confidence`等、指示書11章の「Problem
  Confidence / Need Confidence / Solution Confidence」に近い多軸分類が
  既にある。
* `compute_legacy_escalation_reasons()`: **なぜ**確認が必要かという理由を
  複数列挙できる(指示書12章のQuestion Policyの土台になる)。

ただし現状これらは`pipeline_orchestrator.py`の`_should_escalate_for_
low_confidence()`という**単一のbool判定**(「聞くか聞かないか」)にしか
使われておらず、「複数の理由のうちどれを・どの順で・何回まで聞くか」
という指示書12章のQuestion Policyそのものはまだ存在しない。

### A.4. 「UPDATE」(生成後に会話で育てる)は構造的に存在しない

指示書6章・16章・18章が中心に据える「Held状態から会話に戻り、既存の
道具を更新する」という操作は、**バックエンドに一切存在しない**。

現状生成後にできることは:
* `frontend/lib/features/app_library/data/repositories/
  shared_preferences_app_library_repository.dart`(TD30)による、
  **実行時の入力値(State)のローカル永続化のみ**(「昨日入力した
  買い物リストの中身」が消えない、という程度)。
* Forge Document自体(Widget構成・Schema)を、生成後に自然言語の
  変更要求で書き換える経路は存在しない。「よく買うものを上に置きたい」
  と言われても、今のForgeは**もう一度ゼロから作り直すことしかできない**
  (しかも既存のRecordデータを引き継がない)。

これは指示書が要求する「育てる」体験の中核が丸ごと欠けているという
意味で、このドキュメントが監査した中で**最も大きいギャップ**である。

### A.5. LLM呼び出しの形は「1回のStructured Output」に近い設計思想を既に持つ

指示書21章「毎回5回LLMを呼ぶ必要はない、1回のStructured Outputで
返す方式も検討する」は、既存の`GeminiProvider.complete_structured()`
(`backend/app/ai/foundation/providers.py`、`responseSchema`付き
`generateContent`呼び出し)がまさにこの形の呼び出しを既に実装済みで
あり、Cognitive Pipeline自体は複数段階(Meaning/Intent/Planner/
Compiler)に分かれているが、そのうち実際にLLMを呼ぶのはCompile段階のみ
(`forge_ai/core/pipeline.py`の`_default_cognitive_dependencies()`
docstring、このセッション以前に確認済み)。つまり「1回のLLM呼び出しで
多くを済ませる」という設計思想は、既にこのプロジェクトの一貫した方針
であり、指示書の要求と矛盾しない。

新規のConversation Engineも、1ターンあたり1回の`complete_structured()`
呼び出しに収める(詳細はPhase B)。

### A.6. Repair EngineはLLMの応答を実際には使っていない(正直な事実確認)

余談だが今回の監査で判明した事実として記録する: `forge_ai/repair/
repair_engine.py`の`_try_fix()`は、`provider.complete()`の戻り値を
一切参照せず(`# Mock実装では戻り値は使わず、決定的修正のみ行う`と
コード中に明記)、既知の2パターンのみを決定的に修正する。つまり
「LLMに既存の構造化データを渡し、修正済みの構造化データを受け取る」
という往復は、このリポジトリに**まだ一度も実装されたことがない**。
Phase B以降で設計する「Question Policy」「UPDATE」は、この種の往復を
初めて実装することになる(前例が無い分、リスクとして正直に扱う。
Phase Eのスコープ決定に影響している)。

### A.7. Inspiration Cardsは既にテンプレート的ではない生成ロジックを持つ

指示書24章は「Todoを作る」的なテンプレートカードを再設計せよと
求めるが、`mock_generation_datasource.dart`側は既に8種の「困りごとの
入口」的なカード文言(「買い物で何買うか忘れる」等、CHANGELOG Task003
参照)を持っている。完全な再設計は不要で、「カードを押したら即生成」
ではなく「カードを押したら会話が始まる」という**遷移先の変更**が
必要になる(UIの変更、Phase Eのスコープ外、Phase C参照)。

---

## Phase B. Conversation Architecture

### B.1. 設計方針: 「置き換え」ではなく「薄い意思決定層」を上に足す

指示書20章「既存責務と統合できるなら新しいModuleを乱立させないこと」
に従い、Cognitive Pipeline(Meaning/Intent/Domain分類/Planner/Compiler/
Validator/Repair/Critic)は**一切変更しない**。新設するのは、その手前に
立つ薄い意思決定層(Conversation Engine)と、その後ろに立つ新機能
(Forming Operation = UPDATE)の2つだけである。

```
(新設) Conversation Engine                (既存、無変更)
┌─────────────────────────┐   build_brief   ┌──────────────────────────┐
│ ConversationSession       │ ───────────────▶ │ PromptPipeline.run()      │
│  (turns, NeedModel)       │                  │  run_cognitive_pipeline() │
│ 1回のcomplete_structured()│ ◀─────────────── │  Validator/Repair/Critic  │
│  → ASK | BUILD            │  ForgeDocument   └──────────────────────────┘
└─────────────────────────┘
```

Conversation Engineの仕事は「聞くか、作るか」を決め、作る場合は
**会話全体を1つの自然文(build_brief)へ要約して、既存のPromptPipelineへ
渡す**ことだけである。Forge Language・Validator・Repair・Domain
分類・Widget知識を一切持たない(既存のCognitive Pipelineが既にこれらを
全て持っているため、重複させない)。

### B.2. 型契約

#### ConversationTurn
```python
role: Literal["user", "forge"]
text: str
```

#### NeedModel(指示書9章の概念例を、既存アーキテクチャに合わせて具体化)
```python
problem: str | None          # 「買うものを忘れる」
known: dict[str, bool]       # {"needs_item_add": True, "needs_check": True}
unknown_important: list[str] # まだ埋まっていない、Solutionを左右する項目
safe_assumptions: list[str]  # Forgeが勝手に決めてよい項目(記録のみ、確認しない)
confidence: float            # 0.0-1.0、後述
```

`confidence`は指示書11章の警告どおり、LLMの自己申告値を**そのまま
信用しない**。`forge_ai/core/orchestration/confidence.py`の
`compute_legacy_escalation_reasons()`と同じ思想で、以下の決定的な
シグナルと組み合わせる(Phase Eでは簡略版、後述):

* `unknown_important`が空 → 決定的に+
* ターン数が一定以上(質問しても情報が増えない兆候) → 決定的に+
* LLM自己申告値はあくまで一因子として使う(唯一の判断根拠にしない)

#### ASK / BUILD / UPDATE / CONFIRM契約(指示書22章)

```python
class ConversationAction(str, Enum):
    ASK = "ask"          # 重要情報が不足。1問だけ聞く。
    BUILD = "build"       # 十分理解した。Smallest Useful Toolを生成する。
    UPDATE = "update"     # 既存Toolへの変更要求(Held→Forming)。
    CONFIRM = "confirm"   # 外部作用・不可逆操作の明示確認(指示書19章)。
```

`CONFIRM`は指示書19章が列挙する「金銭・外部送信・個人情報共有・公開・
削除」等に該当する場合のみ発火する。現在Forgeが生成する7 Curated
Domain(fishing_log/household_budget/habit_tracking/todo/reading_log/
inventory/diary)はいずれもローカル完結・不可逆操作を伴わないため、
Phase Eの時点では`CONFIRM`は**型としてのみ定義し、実際に発火する
経路は実装しない**(発火条件が無いのに実装だけ先行させると、
検証できないコードが残るという、TD37と同じ失敗パターンになるため)。

### B.3. Question Policy(指示書12章)

指示書が提示するEIG × Impact ÷ Frictionという評価式は、Phase Eの
時点では**そのままの数式としては実装しない**(実測データが無い状態で
係数を作ると、TD31・TD32のような「実は機能していない」形骸化した
数式になるリスクが高いと判断した——このプロジェクトが繰り返し発見
してきた失敗パターン)。

代わりに、既存の`compute_legacy_escalation_reasons()`と同じ「決定的
ルールで理由を列挙する」設計を踏襲した、簡略版のQuestion Policyを
Phase Eで実装する:

1. LLM(1回のcomplete_structured呼び出し)が、会話全体から
   `unknown_important`(Solutionを大きく左右する未確定事項)を
   最大1件だけ選んで返す(「複数candidateのうち最重要な1件を選ぶ」
   判断自体はLLMに委ねるが、「聞くかどうか」の最終判断は下記の
   決定的ルールで行う)。
2. `unknown_important`が空、またはターン数が`MAX_CONVERSATION_TURNS`
   (Phase Eでは3、`MAX_CONFIRMATION_ROUNDS`と同じ値を踏襲)に達した
   → 強制的にBUILDへ倒す(指示書18章「Smallest Useful Tool」の
   精神——無限に聞き続けない)。
3. それ以外はASK。

将来、実際の会話ログが蓄積された段階で、EIG的な優先度づけを
データドリブンに再設計する(Phase Eの完了時点でTECH_DEBTとして
明示的に記録する)。

### B.4. Forming Operation(UPDATE、指示書16章)— 設計のみ、Phase Eでは実装しない

**技術的リスクを先に明示する**: UPDATE操作は「既存のForge Document
(JSON)全体 + 変更要求」を入力に、更新済みのForge Document全体を
出力する必要がある。Forge DocumentのWidget木は`children`を持つ
再帰的な構造(`ForgeWidgetNode`のsealed class、複数のUnion型)であり、
Gemini `responseSchema`(OpenAPI Schemaのサブセット、`$ref`による
自己参照未対応)で無制限の再帰的Widget木を直接構造化出力させられるかは
**未検証**である。検証を経ずに実装だけ進めると、TD37と同種の「実は
一度も動いていない機能」を生む危険が高いと判断し、Phase Eでは
**実装を見送り、次の一手として明示的に切り出す**(TECH_DEBT.md
TD40参照)。

設計としては以下を推奨する(実装前に必ず技術検証すること):

* 案1(推奨): Forge Document全体を書き換えさせず、`add_field`
  ・`reorder_records`・`add_widget`(Widget Registryから選択)・
  `change_property`という**小さなOperationの集合(DSL)**をLLMに
  選ばせる。DSLは非再帰的なフラット構造なので`responseSchema`との
  相性がよく、適用後は既存の`schema_validator.py`でそのまま検証できる。
* 案2: Document全体を書き換えさせるが、`responseSchema`を使わず
  素朴なJSON文字列生成+`json.loads()`(`MockLLMAdapter`ではなく、
  Gemini自体が`responseMimeType: application/json`のみで
  `responseSchema`無しの自由出力を返す設定)にする。Schema制約を失う
  代わりに再帰の制約から解放される。検証はValidator+既存のRepair
  往復回数制御パターンを流用する。

いずれの案も「LLMに既存の構造化データを渡し、修正済みデータを
受け取る」という、A.6で確認した通りこのリポジトリに前例のない往復を
新規実装することになるため、Phase Eとは別のセッションで、小さく
検証しながら進めることを推奨する。

---

## Phase C. UX Flow

### C.1. Space / Forming / Held の既存画面へのマッピング

新しい概念名を無理に全面採用するのではなく、既存画面が既に近い役割を
担っていることを確認した上でマッピングする:

| 新概念 | 既存の対応物 | 変更点 |
|---|---|---|
| Space | Home画面 | 「何のアプリを作りますか」ではなく「最近、困ってることある？」に近い導入文言へ(Phase E範囲外、UI文言変更のみで済む) |
| Forming | Home→(会話)→Generating、および生成後の変更要求 | 現状は「1入力→即座に生成 or 最大3往復の確認」のみ。新設するConversation Engine(本ドキュメントB章)を挟むことで、複数ターンの自然な会話に拡張する。UPDATE(B.4)が実装されればHeldから再突入できる |
| Held | GeneratedAppScreen / ToolScreen相当 | 変更なし。「完成」ではなく「今はここで止まっている」という位置づけの明文化のみ |

### C.2. 最小フロー(指示書Phase Cの要求)

```
起動 → Space(困りごとを話せる場所)
  ↓ ユーザー発話
Forming: ConversationEngine.step()
  ├─ ASK   → 1問だけ聞く → ユーザー回答 → 再度step()
  ├─ BUILD → build_briefを既存PromptPipelineへ → ForgeDocument
  └─ (CONFIRM: 型のみ、Phase E未実装)
  ↓
Held(「はい、どうぞ」)
  ↓ ユーザー「ここ変えて」
Forming(UPDATE、Phase B.4設計のみ・未実装)
  ↓
Held(更新済み)
```

### C.3. Confirm Screen(指示書23章)の扱い

指示書23章は「毎回の確認画面」が「はい、どうぞ」体験を弱めると
指摘する。現状の`needs_confirmation`は、既に**確認が必要な場合のみ**
発火する設計(A.2)であり、「毎回」ではない。したがって既存のConfirm
的UIを完全に削除する必要はなく、**「ASK」が発火した場合にだけ
自然な会話 turnとして表示し、発火しない場合は素通りする**という、
現状に近い形で十分に指示書の要求を満たせる。

Prototypeの主要体験(Home→生成→Tool)自体を削除する提案ではないため、
指示書28章が挙げる「Prototypeの主要体験を完全削除」には該当しない
——ただし、Home画面の導入文言・Inspiration Cardsの遷移先を「会話」に
変えることは、UXの第一印象を変える意思決定であり、CEOへの確認事項
として明示する(このドキュメント末尾、report.mdのDecision Log参照)。

---

## Phase D. Forge Architecture Integration

### D.1. 何を変更しないか(重要)

* `forge_ai/core/`配下(Meaning/Intent/Domain分類/Planner/Compiler/
  World Model/Lexicon)は無変更。Conversation Engineはこれらを一切
  importしない。
* `forge_ai/repair/`・`forge_ai/quality/`も無変更。
* 既存の`POST /api/v1/ai/generate`・`POST /api/v1/ai/generate/confirm`
  も無変更(後方互換、既存Frontendはそのまま動く)。

### D.2. 何を新設するか

* `backend/app/ai/runtime/conversation_types.py`: `ConversationTurn`・
  `NeedModel`・`ConversationAction`。
* `backend/app/ai/runtime/conversation_engine.py`:
  `ConversationEngine.step()`。1ターンにつき`GeminiProvider.
  complete_structured()`を1回呼ぶ。ASKなら質問を返す。BUILDなら
  `build_brief`を`PromptPipeline.run()`へそのまま渡す(既存資産の
  完全再利用)。
* `backend/app/ai/runtime/conversation_store.py`: `ConfirmationStore`
  (`confirmation_store.py`)と同じ設計(プロセス内メモリ・TTL・
  最大ターン数)を、会話セッション用に踏襲する。DBは追加しない
  (共通指示書の既存方針を継続)。
* `POST /api/v1/ai/converse`: 新規・追加のみのエンドポイント。
  既存の`/generate`系とは独立して動く。

### D.3. Provider非依存性(ADR-006)の維持

Conversation Engineは`GeminiProvider`を直接使うのではなく、既存の
`ProviderRouter`/`LLMAdapter`Protocol経由で呼ぶ(Mock Providerでの
Unit Test・将来の他社LLM差し替えを、既存のCognitive Pipelineと同じ
形で可能にする)。

---

## リスクと未解決事項(正直な申告)

1. **UPDATE(Forming Operation)は設計のみで未実装**(B.4)。指示書が
   要求するE2Eフロー(「よく買うものを上に置きたい」→更新)の後半
   ターンは、Phase Eでは実現できない。
2. **Question Policyは簡略版**(B.3)。指示書12章のEIG×Impact÷Friction
   という評価式そのものは実装していない。実データが無い状態で係数を
   決め打ちすると形骸化するリスクがあるとの判断。
3. **フロントエンドは変更しない**(Phase Eはbackendのみ)。新しい
   `/converse`エンドポイントは、実際にHome画面から呼ばれるようになる
   までは、CEOにもエンドユーザーにも体験として届かない。
4. **Product Metrics(指示書25章)は未計測**。ログ基盤(平均質問回数・
   初回Tool採用率等)の設計・実装は本ラウンドのスコープ外。
