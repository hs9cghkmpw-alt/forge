# AI Runtime(backend/app/ai/runtime/）

FORGE-MILESTONE-003「Analyzer Zero → Chrome Verification → Native AI Foundation」
PHASE6〜9で追加した、Forge Native AIのための土台。**このドキュメントが説明する
コードは、実際のLLM推論を一切含まない。** 全てProtocol(責務定義)と、
呼ばれると`NotImplementedError`を送出するStubである。

---

## 1. なぜbackend/app/ai/foundation/と別にruntime/を作ったか

FORGE-MILESTONE-002で`backend/app/ai/foundation/interfaces.py`を既に作っていた。
今回`runtime/`を追加するにあたり、**型を複製しない**という原則を最優先した。

| 概念 | 既存(foundation/) | 今回(runtime/) | 関係 |
|---|---|---|---|
| 自然言語→Intent→Plan | `IntentPlanner` + `ProductPlanner`(2つのProtocol) | `AIPlanner`(1つのProtocol) | `runtime/planner.py`が2段階を1つの窓口へ統合。型(`IntentIR`/`PlanIR`)はそのままエイリアス(`Intent`/`Plan`)として再利用 |
| Plan→JSON | `LanguageGenerator` | (同じものを再利用) | 新規定義せず、`foundation/interfaces.py`のものをそのまま使う |
| 品質評価 | `Critic` | `AICritic` | `CriticResult`型は再利用、Protocol名のみ`runtime/`の命名規則(`AI`接頭辞)に統一 |
| 修復 | `RepairEngine`(`dict`を直接返す) | `AIRepair`(`RepairResult`という構造化型を返す) | **新規追加**。理由は4章 |
| Provider解決 | (無かった) | `ProviderRouter` | **新規追加**。5 Provider名からの解決ロジック(実際に動作する) |
| 文脈構築 | `Memory` + `Conversation`(個別のProtocol) | `AIContextBuilder` | **新規追加**。2つの情報源を1回のプロンプト用に統合する責務が無かった |
| 全体オーケストレーション | (無かった、コメントで「将来追加予定」と記述されていた) | `PromptPipeline` | **新規追加**。PHASE9のフローを実行する薄い関数 |

`foundation/`は削除していない(既存テスト`test_ai_foundation.py`の5件は
無改変のまま引き続き合格する)。`runtime/`は`foundation/`を**置き換える**
のではなく、**その上に、より完全なオーケストレーション層を追加した**もの、
という位置づけである。

---

## 2. モジュール一覧

| ファイル | Protocol | Stub | 新規/既存型の再利用 |
|---|---|---|---|
| `intent_parser.py`(FORGE-MILESTONE-004) | `IntentParser` | `StubIntentParser` | `IntentIR`(既存を再利用) |
| `planner.py` | `AIPlanner` | `StubAIPlanner` | `Intent`=`IntentIR`、`Plan`=`PlanIR`(再利用) |
| `template_engine.py`(FORGE-MILESTONE-004) | — | — | `Template`/`TemplateRegistry`は**実装済み**(既存3 Template関数のカタログ化のみ、AI推論を含まない) |
| `template_selector.py`(FORGE-MILESTONE-004) | `TemplateSelector` | `StubTemplateSelector` | 新規 |
| `critic.py` | `AICritic` | `StubAICritic` | `CriticResult`(再利用) |
| `repair.py` | `AIRepair` | `StubAIRepair` | `RepairResult`(新規、4章参照) |
| `context_builder.py` | `AIContextBuilder` | `StubAIContextBuilder` | `PromptContext`(新規) |
| `provider_router.py` | (`AIProviderFactory`) | `ProviderRouter`(実装済み、5章参照) | `AIProvider`=`LLMAdapter`(再利用)。FORGE-MILESTONE-004で`native`/`local`エイリアス追加 |
| `native_ai_runtime.py`(FORGE-MILESTONE-004) | — | `NativeAIRuntime` | 上記全てを束ねる、判断ロジックを持たないbundle |
| `prompt_pipeline.py` | — | `PromptPipeline`(オーケストレーションのみ実装済み) | 全て上記を組み合わせる |

---

## 3. FORGE-MILESTONE-004(Native AI Phase-1)で追加したもの

- **`IntentIR`拡張**(`foundation/interfaces.py`): `entities`/`platform`
  (`Platform` Enum)/`complexity`(`Complexity` Enum)/`category`/
  `output_type`の5フィールドを追加した。全て既定値を持ち、既存の
  `IntentIR(purpose="x")`という呼び出しは変更せずそのまま動く。
- **`IntentParser`**(`intent_parser.py`、新規): 「自然言語→Intent」だけを
  担当する、`AIPlanner`より粒度の細かいProtocol。`AIPlanner`は削除・
  変更していない(後方互換性維持)。
- **`Template`/`TemplateRegistry`**(`template_engine.py`、新規):
  既存3 Template(checklist/memo/form)を、Category/Priority/
  Capabilities/Required Widgets/Optional Widgets/Tagsという構造化
  メタデータでカタログ化した。**新しいTemplate実装は追加していない**
  (既存の`build_checklist_template`等への薄い委譲のみ)。
- **`TemplateSelector`**(`template_selector.py`、新規): IntentIR/PlanIRから
  最適なTemplateを選ぶ契約。Stub。
- **`ProviderRouter`のエイリアス追加**: `native`→`forge_ai`と同一インスタンス、
  `local`→`oss`と同一インスタンス。新しいProvider実装は追加していない。
- **`NativeAIRuntime`**(`native_ai_runtime.py`、新規): 上記全てを束ねる
  bundle。`is_fully_stubbed()`という、推論系コンポーネントが全てStubの
  ままであることを機械的に検証できるメソッドを持つ(「動いたふりを
  していないか」を実際にテストで確認できるようにするための工夫)。

---
## 4. `RepairResult`を新規追加した理由

既存の`RepairEngine.repair()`は`dict[str, Any]`をそのまま返す設計だった。
Prompt Pipelineが「何件直せたか」「あと何件残っているか」「最終的に
成功したか」を**型で**判定できないと、`prompt_pipeline.py`のRepair Loop
(`docs/spec/PROMPT_PIPELINE.md` 3章参照)が「合格したかどうか」を`dict`の
中身を都度パースして判定する羽目になり、責務が曖昧になる。そのため
`RepairResult`という構造化型を新規追加した(既存に同名・同義の型は
無いため、これは複製ではなく正当な追加と判断した)。

---

## 5. `ProviderRouter`が実際に動作するコードである理由

PHASE7は「実装は禁止」だが、`ProviderRouter`の**ルーティング(選択)ロジック**
自体はAI推論ではない(文字列キーから辞書を引くだけの処理)。禁止事項
「AI実装したふり」が指しているのは**推論そのもの**(Providerを実際に
呼び出した結果)であり、「どのProviderを使うかを決める」というのは
AI推論を一切含まない、普通のプログラムロジックである。

この区別を明確にするため、`ProviderRouter.resolve()`は実際に動作するが、
その戻り値(`AIProvider`)の`complete_structured()`を実際に呼ぶと、
`foundation/providers.py`の既存スタブが`NotImplementedError`を送出する
(`tests/test_ai_runtime.py`の`test_all_foundation_provider_stubs_raise`で
5 Provider全件を確認済み)。

---

## 6. Provider非依存であることの確認

`provider_router.py`のソースコードに、OpenAI/Anthropic/Google等のSDK
importが無いことを、実際にソースコードを検査するテスト
(`test_no_provider_specific_sdk_imported`)で確認している。

`ProviderRouter.default_provider_name()`は`"forge_ai"`を返す。これは
「ChatGPT/Claude/Geminiを前提にしない、最終的にForge Native AIを使う」
という最重要方針を、コードの既定値としても表現したものである。
