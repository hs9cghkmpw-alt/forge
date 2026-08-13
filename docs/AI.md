# AI設計方針

## 1. 大原則

**AIはコードを一切生成しない。AIが生成するのはJSON UI Schemaのみ。**

理由:
- コード生成は実行環境・セキュリティリスク・ビルド管理が複雑になる。
- JSONに制約することで、Flutter側で安全にサンドボックス的に解釈・検証できる。
- JSONはバージョン管理・差分比較・AIによる自己改善（AI Improve）と相性が良い。

## 2. 責務分担

| 主体 | 責務 |
|---|---|
| AI | 会話の意図を解釈し、JSON UI Schemaを生成・修正する |
| Backend (FastAPI) | AI呼び出しの仲介、生成されたJSONの検証・保存・バージョン管理 |
| Frontend (Flutter) | JSON UI Schemaを解釈し、Widgetツリーとしてレンダリングする |

AIは **JSON Schemaという「契約」の中でのみ自由** であり、
契約外の出力（任意コード・任意ファイル操作など）は許可しない。

## 3. JSON UI Schema の設計方針（概略）

- `shared/schemas/` にJSON Schema（JSON Schema仕様）として定義し、Frontend/Backend双方が同じ定義を参照する。
- v1で確定した実際の最小構造(Task003。`shared/schemas/ui_schema.v1.json`参照。
  以前ここにあった例は`screen`が単数・`"type": "screen"`付きだったが、実装したv1とは
  形が異なっていたため、実際のSchemaに合わせて更新した):

```json
{
  "version": "1.0",
  "app": { "title": "買い物メモ" },
  "initial_screen_id": "shopping_list",
  "screens": [
    {
      "id": "shopping_list",
      "title": "買い物メモ",
      "state": {
        "items": { "type": "checklist", "value": [] }
      },
      "body": {
        "type": "column",
        "id": "root",
        "children": [
          { "type": "checklist", "id": "list", "state_ref": "items" }
        ]
      }
    }
  ]
}
```

`screen`はWidgetのtype一覧には含まれない(`text`/`text_field`/`button`/`column`/`row`/
`checklist`の6種類のみ)。`screens`は配列であり、`initial_screen_id`が最初に表示する
画面を指す。詳細は `docs/DECISIONS.md` D2・D3、統合レポート「Forge Language v1」章を参照。

- Backendは受け取ったJSONを `shared/schemas/` の定義に対してバリデーションしてから保存する。
- Flutterの `json_ui/widget_registry/` が `"type"` の値をキーにWidgetを解決する
  （未知の`type`は安全に無視 or フォールバックWidgetを表示）。

## 4. AIの安全境界

- AIの出力は必ずJSON Schemaバリデーションを通過させる（Backend側の責務）。
- バリデーションに失敗したJSONはユーザーに返さず、再生成 or エラー表示にフォールバックする。
- AIに外部実行権限・ファイルシステムアクセス・任意コード実行権限を与えない。

## 5. 将来機能との関係

- **AI Memory**: 過去の会話・生成履歴を `ai_conversations` / `ai_memories` に保存し、
  次回生成時のコンテキストとして利用する（今フェーズでは未実装）。
- **AI Improve**: 既存の `app_versions` を比較し、UI/UX改善のJSON差分を提案する機能。
  「生成」と「改善提案」は別サービス (`services/generation_service.py` /
  `services/improve_service.py`) として分離する想定。

## 6. Conversation Readiness / Question Policy(FORGE-CONVERSATION-READY-001、2026-08-12)

「どこまで聞いたら作るのか」を決める層。実装は
`backend/app/ai/runtime/conversation_policy.py`(判断)と
`conversation_engine.py`(LLM呼び出し1回 + Policyの適用)。

### 6.1 大原則: LLM Proposal < Deterministic System Facts

会話の判断において、**LLMの自己申告は単独では決して根拠にならない**。
`next_action`も`confidence`も「提案」として受け取るだけで、実際の
ASK/BUILD/UPDATE/CONFIRMは、Forge側が事実として知っていること
(`DecisionContext`)から決定的に導出する。

具体的な上書きルール:

| System Fact | 帰結 |
|---|---|
| `has_existing_tool == False` | LLMが`update`と言ってもUPDATE不可(BUILD/ASKへ補正) |
| blocking unknownあり | 原則BUILD不可 |
| external side effectあり | CONFIRM必須 |
| destructive actionあり | CONFIRM必須 |
| Validator blocking error | BUILD完了扱いにしない(`/converse`はエラーを返す) |

### 6.2 Conversation Readiness

`ConversationReadiness`(`conversation_types.py`)は5値:

| 値 | 意味 | Action |
|---|---|---|
| `BUILD_READY` | 重要な未知が無い | BUILD / UPDATE |
| `SAFE_TO_ASSUME` | 残る未知はLOW以下、または質問済みのHIGH | BUILD / UPDATE(仮定を記録) |
| `NEEDS_QUESTION` | 聞くべき(BLOCKING/HIGHかつ未質問の)未知がある | ASK |
| `NEEDS_CONFIRMATION` | 外部作用・不可逆操作を含む | CONFIRM |
| `INSUFFICIENT_INFORMATION` | BLOCKINGが質問済みでも未解消 | ASK(**決してBUILDしない**) |

判定順序は「安全性 → 質問 → 未解消blocking → 仮定 → 完了」であり、
`evaluate_readiness()`がこの順に評価する。

### 6.3 Question Policy

未知には`UnknownImpact`(blocking / high / low / cosmetic)を必ず付ける。

* 質問するのは`blocking`・`high`のみ。
* `low`はSafe Assumption候補。
* `cosmetic`(色・レイアウト・ボタンの位置)は**Design Systemの領分**で
  あり、決して質問しない。
* 同じUnknownを言い換えて繰り返し質問しない
  (`ConversationSession.asked_question_keys`で抑止)。

### 6.4 Safe Assumption

聞かずに決めたことは、必ず`key` / `value` / `reason`の3点で記録する
(`SafeAssumption`)。Debug・Golden Test・Product Analytics・将来のAI
学習で判断根拠を追えるようにするため。

### 6.5 MAX_CONVERSATION_TURNSの新しい意味

**旧**: この回数に達したら強制的にBUILDへ倒す上限。
**新**: この回数に達したら**質問戦略を変える**閾値。

「質問しすぎない」と「分からなくても作る」は別である。閾値に達したとき
変わるのは質問の仕方だけで、BUILDの可否はReadinessが決める:

* `high`は質問をやめ、理由付きのSafe Assumptionへ回す。
* 残る質問は自由回答ではなく短い二択にする。
* `blocking`は閾値に達しても**質問し続ける**。

### 6.6 Build Failure Fallback

BUILD判定後にPipelineが失敗した場合、`classify_build_failure()`が
「追加質問で解消しうるか」を判定する。

* 理解段階(normalization / ambiguity / domain / intent / meaning)の
  失敗 → ASKへ戻す(「少しだけ確認させて。」)。
* 生成段階(Forge Language生成 / Validator / Repair)の失敗 → 安全な
  エラー表示。**AIの失敗をユーザーの情報不足のように見せない**。
* Provider障害(rate_limited / unavailable)→ 追加質問では直らないため
  エラー表示。

## 7. Solution Shape(2026-08-12)

「いつ作るか」(Readiness)と対になる、「**何を作るか**」の判断。
実装は`forge_ai/core/ir/solution_shape.py`。

| Shape | 形 | 条件 |
|---|---|---|
| `CHECKLIST` | 1画面・タブ無し・入力欄1つ・チェックリスト | 文字列1つ、または文字列1つ+真偽値1つ |
| `RECORD_CRUD` | 追加/一覧/編集の3タブ・型付きフォーム・一覧・グラフ | それ以外 |

**判定材料をEntityのFieldに限っている理由**: ユーザーの言葉
(「数えたい」「チェックしたい」)から直接選ぶと表現の揺れに弱く、
同じニーズでも言い方次第で形が変わる。Entityは会話と
EntitySynthesizerを通って煮詰まった結果であり、「属性が1つしかない」
=「並べてチェックするだけで足りる」という対応が構造的に安定している。

**軽くしすぎて情報を捨てない**: `CHECKLIST`にするのは、`checklist`
Stateの1項目`{id, text, done}`で情報を落とさず表現しきれる場合だけ。
日付や金額を持つEntityをchecklistへ押し込むと、ユーザーが記録したかった
情報が消える。形を軽くすることと情報を捨てることは別である。

**カウンタ形が無い理由**: Forge Languageの`ACTION_TYPES`には
`set_value`(固定値の代入)しか無く、`count + 1`という動的な加算を
表現できない。作ると「押しても増えないボタン」になるため、Runtimeに
increment相当が入るまでは`RECORD_CRUD`で代用する。

## 8. Model Gateway / Provider独立性(FORGE-QUALITY-AI-INDEPENDENCE-003)

    Forge Brain → Model Gateway → Provider(Gemini / Local / Mock)

**Geminiは一Providerに過ぎない**。上位ロジック(Conversation Policy /
Readiness / Validator / Safety)はProviderを一切知らない。

### 8.1 既存抽象を作り直していない

監査の結果、`LLMAdapter.complete_structured(prompt, response_schema)
-> dict`は既にProvider非依存であり、`ConversationEngine`・
`ForgeOperationEngine`はProvider実装を知らなかった。Gatewayが埋めたのは
**足りなかった4点だけ**である:

| 不足 | Gatewayが足したもの |
|---|---|
| Task概念が無い | `ForgeTask`(Task単位のRouting・評価) |
| 計測が無い | latency / 失敗率 / schema適合率 |
| Fallbackが無い | primary失敗時に次のProviderへ |
| Routingが無い | `TaskRoute`(Task別のprimary/fallback) |

### 8.2 Task単位でしか評価しない

「GeminiとLocalのどちらが優秀か」という比較は行わない。Benchmarkも
Routingも`(task, provider)`の組でのみ成立する。

### 8.3 採用条件

`BenchmarkReport.winner()`は、**schema適合率90%以上かつ正答率50%以上**
のProviderしか勝者にしない。形式が整っているだけのProvider(例:
`mock`は適合率100%・正答率0%)を採用しないため。

### 8.4 Local Provider

`LocalModelProvider`はOpenAI互換`/v1/chat/completions`を叩く。
**Ollama固定ではない**(llama.cpp・LM Studio・vLLMも`base_url`変更のみ)。
小さいモデルがコードフェンス付きで返す等に耐えるJSON抽出を持ち、
パースできなければ**例外**にする(空dictを返して成功に見せかけない、
TD40の教訓)。

セットアップと実行手順: `docs/development/LOCAL_MODEL_SETUP.md`

## 9. Scripted Conversation Set(§26)

実ユーザーデータが無くても会話品質を測り続けるための50セッション
(`backend/app/ai/gateway/conversation_dataset.py`)。

明確な要求10 / 曖昧10 / 分からない5 / 任せる5 / どっちでもいい5 /
無関係回答5 / 途中変更3 / UPDATE 4 / 高リスク3。

測定項目は§26のとおり(平均質問数・繰り返し質問・縮退回数・
CONFIRM数・build失敗数等)。`run_session(llm=...)`でLLMを差し替えれば、
同じ台本のままGemini vs Localの会話品質比較にも再利用できる。

**このデータセットは、最初に走らせた時点でPolicyの実バグを3件検出した**
(委任検出が段を止めていた・BUILD経路でstrategyを落としていた・
委任判定が最新発話のみだった)。現在の集計値:

| 指標 | 値 |
|---|---|
| 平均質問数 | 1.20 |
| 繰り返し質問 | 0 |
| 縮退発動 | 20 |
| 未決着 | 0 |
| build失敗 | 0 |
