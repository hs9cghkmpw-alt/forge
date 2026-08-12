# FORGE-PRODUCT-VISION-002 — 「困りごとを話すと道具が生まれるAI」への製品思想更新 実施レポート

2026-08-11。CEO指示書への対応。設計(Phase A〜D)は`docs/spec/
FORGE_PRODUCT_VISION_002_CONVERSATIONAL_ARCHITECTURE.md`・
`docs/adr/ADR-014-conversation-engine-wraps-not-replaces-pipeline.md`
に記録済み。本レポートはPhase E(実装)の結果と、指示書29章が要求する
最終報告事項をまとめる。

## 1. 監査結果の要約(Phase A)

現物を実際に読んで確認した事実:

* 「Space/Forming/Held」という語彙はリポジトリのどこにも存在しない
  (新規導入)。
* 「ASK」に相当する仕組み(`needs_confirmation`、最大3往復)は既に
  存在するが、単発の曖昧さ検出に紐づく脇道であり、複数ターンの
  自然な会話としては設計されていない。
* Confidence計算基盤(`forge_ai/core/orchestration/confidence.py`、
  ADR-007)は既に成熟しており、指示書11章の思想(LLM自己申告を鵜呑み
  にしない)と一致する。
* 「UPDATE」(生成後に会話で育てる)は**バックエンドに一切存在しない**
  ——最大のギャップ。
* Repair Engine(`forge_ai/repair/repair_engine.py`)は、LLMの応答を
  実際には使っておらず決定的修正のみ行っている(正直な事実確認。
  「LLMに構造化データを渡し修正済みデータを受け取る」往復は、この
  リポジトリに前例が無い)。

詳細は design doc Phase A参照。

## 2. 実装したもの(Phase E)

ADR-014の決定に従い、既存Cognitive Pipelineは**一切変更せず**、その
手前に立つ薄い意思決定層を新設した。

* `backend/app/ai/runtime/conversation_types.py`: `ConversationTurn`・
  `NeedModel`・`ConversationAction`(ASK/BUILD/UPDATE/CONFIRM、後2つは
  型のみ)・`ConversationStepResult`・`ConversationSession`。
* `backend/app/ai/runtime/conversation_store.py`: `ConversationStore`
  (`confirmation_store.py`と同じ設計、プロセス内メモリ・TTL 30分・
  最大3ターン)。
* `backend/app/ai/runtime/conversation_engine.py`: `ConversationEngine.
  step()`。1ターンにつき`AIProvider.complete_structured()`を1回だけ
  呼ぶ(指示書21章)。LLMの`next_action`自己申告をそのまま信用せず、
  `unknown_important`が空、またはターン数上限到達で強制的にBUILDへ
  倒す決定的な上書きルールを持つ(design doc B.3)。
* `backend/app/ai/runtime/pipeline_errors.py`: `ConversationSessionError`
  追加(既存の`ConfirmationSessionError`と対称)。
* `backend/app/schemas/ai.py`: `ConverseRequest`・`ConverseAskResponse`・
  `ConverseBuildResponse`・`NeedModelDTO`追加。
* `backend/app/routers/ai.py`: `POST /api/v1/ai/converse`追加。BUILDと
  判定した場合、会話全体を要約した`build_brief`を既存の
  `PromptPipeline.run()`へそのまま渡す(Forge Language・Validator・
  Domain知識は一切持たない)。既存Cognitive Pipeline側がさらに
  `needs_confirmation`を返した場合は、既存の`/generate/confirm`契約へ
  そのまま委ねる(新しい確認UIを作らず、既存資産を再利用)。

既存の`POST /api/v1/ai/generate`・`/generate/confirm`は**無変更**、
既存435 Dart + 624 Python(新規42件含む)のテストは全て緑のまま
(後方互換)。

## 3. テスト結果

* `backend/tests/test_conversation_store.py`(12件、新規)・
  `backend/tests/test_conversation_engine.py`(9件、新規、Fake
  Providerで決定的にASK/BUILD分岐・上書きルールを検証)、いずれも
  green。
* 既存backend全テスト: 624件(新規18件含む)、624 passed。
* forge_ai全テスト: 無変更・451 passed(このドキュメント作成時点で
  再確認)。
* Dart側: 無変更(Phase Eはbackendのみ、design doc D.1「フロントエンドは
  変更しない」)。

## 4. 実機確認(uvicorn + 実Gemini、2026-08-11実施)

3つの会話を実際にGemini経由で流し、指示書の理想例(2章)・Smallest
Useful Tool例(18章)・良い質問の例(5章、薬の例)それぞれに近い
入力で検証した。

### 4.1 「買い物行くと、いつも何買うか忘れるんだよね」(1ターンでBUILD)

`unknown_important`が空(confidence=0.95)と判定され、1ターン目で
即座にBUILD。既存Cognitive Pipelineが`shopping`ドメインへ正しく分類し、
Validator合格の買い物チェックリストアプリを生成した(`checklist`+
`add_item`)。指示書の「質問攻めにしない」原則どおり、必要以上に
聞かなかった。

### 4.2 「薬を飲むのを飲むのを忘れちゃうんだよね」(既存Pipeline側の確認が発火)

ConversationEngine自身は`build`と判定したが、`build_brief`を渡した
先の既存Cognitive Pipelineが独自に`priority1_privacy_safety_permission`
(「薬」という機微語)を検出し、`needs_confirmation`を返した。`/converse`
エンドポイントはこれをそのまま`GenerateNeedsConfirmationResponse`として
返し、既存の`/generate/confirm`で続行可能であることを確認した。

**正直な評価**: ConversationEngine自身のQuestion Policyは、指示書5章が
理想とする「飲んだかどうかだけ分かればいい？それとも時間になったら
知らせてほしい？」のような、Solutionの形を左右する質問を**自発的には
選ばなかった**(むしろ即BUILD判定だった)。安全に止まれたのは、
既存Pipeline側のプライバシー検出という別の防御層のおかげである。
Question Policy(design doc B.3)は簡略版であり、この種の「機微だが
Solutionの分岐点ではない」ケースと「Solutionの分岐点そのもの」を
区別する精度は、まだ指示書の理想に届いていない——次の改善点として
記録する。

### 4.3 「忘れっぽくて困ってる」→「毎朝の持ち物を忘れちゃうんだよね」(2ターンでASK→BUILD)

1ターン目は`unknown_important=["具体的にどのようなシチュエーション...
で一番困っているか"]`でASK(「具体的にどんなことを忘れやすくて
困っていますか？」)。2ターン目のユーザー回答を受けてBUILD、
`build_brief`="毎朝の持ち物忘れを防ぐための...チェックリストアプリ"、
Validator合格。指示書18章の例(「仕事のやること忘れる」→Task List)と
ほぼ同じ形(「毎朝持ち物を忘れる」→チェックリスト)が、実際に会話から
生成されることを確認した。

### 4.4 「よく買うものを上に置きたい。カテゴリ分けもしたい。」(UPDATE、追記: 同日中に実装完了)

4.1で生成した3件の買い物チェックリスト(牛乳・食パン・卵)に対し、
`POST /api/v1/ai/update`(TD40)へ上記の変更要求を送った。1回目は
Validator不合格、2回目(Repair往復1回)でValidator合格。既存3件のitemを
`frequent_items`/`food_items`/`daily_items`という3つのchecklist state
へ正しく分割・再配置し、対応する3つの追加ボタンまで生成した。指示書
6・16・18章が例として挙げる「よく買うものを上に置きたい」「カテゴリ
分けしたい」がそのまま実際に動くことを確認した。詳細はTECH_DEBT.md
TD40の追記参照。

### 4.5 `/converse`と`/update`の結線(追記: 同日中)、実機確認の過程で発見した実バグ3件

4.4で使った変更要求を、今度は`/update`単体ではなく`/converse`
(`current_document`に4.1の生成物を添えて)へ送った。この過程で
Unit Testでは検出できなかった実バグ3件を発見・修正した(TD42に詳細):
`/converse`のProvider呼び出しに例外処理が無く親切なエラーメッセージが
失われる問題、`MockLLMAdapter`が`"number"`型JSON Schemaを処理せず
`float()`変換でクラッシュする問題、新規テストファイルが他の無関係な
テスト(workspace/folder router)を巻き込んで壊すテスト分離問題。
修正後、エラー変換自体(429レート制限→`provider_error`/
`retryable=true`)が正しく動作することは確認したが、Gemini無料枠の
**日次クォータ**をこのセッション全体の検証作業で使い切っており、
「実際にGeminiが会話中でupdateを選ぶ」ところまでのライブE2E確認は
完了できなかった(正直な申告)。分岐ロジック自体は決定的な
FakeProviderによるUnit Test(4件)で確認済み。

## 5. Decision Log(指示書27・28章対応)

以下は、明確に安全・可逆と判断し、CEO確認を待たずに実施した:

* Conversation EngineをCognitive Pipelineの外に置く設計(ADR-014)。
* 新規エンドポイント`/converse`の追加(既存エンドポイント無変更、
  後方互換)。
* Question PolicyのMVP版(EIG×Impact÷Frictionの数式化は見送り、
  決定的な上書きルールのみ実装、design doc B.3)。
* UPDATE(Forming Operation)の技術検証(`responseSchema`の再帰制約を
  実機確認)と、その結果に基づく実装(`GeminiProvider.complete_
  structured()`の拡張、`ForgeOperationEngine`、新規`POST /api/v1/ai/
  update`)。CEO「実装できたの？できるまでやって」という指示を受け、
  当初「次のセッションで検証」としていたTD40を同日中に検証・実装まで
  完了させた。

以下は、当初**CEO確認が必要**と判断し実施しなかったが、CEOから
「指示書28章の確認事項リストのどれにも実際には当てはまらない(可逆な
UI/ロジック変更に過ぎない)」という指摘を受け、同日中に判断を撤回して
実施した:

* ~~フロントエンドの主要導入体験の変更~~ → **実施済み(TD43)**。Home画面
  の見出しを「困ってることある?」的な文言へ変更し、送信の遷移先を
  `ConversationFlowScreen`(複数ターンの会話)へ切り替えた。既存の
  `GenerationFlowScreen`(Home→生成→Tool)は削除せず、コード上に
  残したままにしている(可逆性を優先した設計判断)。

## 6. 残存リスク(正直な申告)

1. ~~UPDATE(Forming Operation)が未実装~~ → 実装・実機確認済み(4.4節、
   TD40)。~~`/converse`とはまだ結線していない~~ → 同日中に結線
   (TD42)。`ConversationEngine.step(session, has_existing_tool=True)`
   が`update`を選び、`/converse`から`ForgeOperationEngine.apply_
   update()`へ委譲する。ただし「実際にGeminiが会話中で自発的にupdate
   を選ぶ」ところまでのライブE2E確認は、Gemini無料枠の日次クォータ
   枯渇のため完了できていない(TD42、代替としてFakeProviderによる
   決定的なUnit Testで分岐ロジック自体は確認済み)。
2. Question Policyが簡略版であり、4.2で確認した通り、Solution分岐点の
   検出精度はまだ指示書の理想に届いていない。
3. ~~`/converse`・`/update`はbackendにのみ存在し、Flutter Frontendから
   はまだ呼ばれていない~~ → **同日中にFrontend統合済み(TD43)**。
   Home画面・`GeneratedAppHostShell`から実際に呼ばれるようになった。
   Widget Test実行で、`ConversationTurnRequest`のキャッシュキーに
   `_sessionId`を含めていたことによる「同じ発話でもう一度`/converse`を
   呼んでしまう」実バグを発見・修正した(目視では気づけない種類の
   バグだった、詳細はTD43)。
4. Product Metrics(指示書25章、平均質問回数等)の計測基盤は未着手。
5. `ConversationStore`はプロセス内メモリのみ(TD41、既存
   `ConfirmationStore`と同じ既知の制限)。
6. `/update`のRepair往復(最大2回)は、Validator不合格の理由をテキストで
   LLMへ見せて再生成させるという、`repair_engine.py`には無い新しい
   パターンである(A.6参照)。今回2回の実機確認(4.4節、うち1回は
   1回目失敗→2回目成功)では機能したが、試行回数はまだ少なく、
   より複雑な変更要求でも安定して収束するかは追加検証が必要。
7. Home画面から新しい会話で建てたUPDATE(会話中の`ConversationAction.
   UPDATE`)は、Gemini無料枠の日次クォータ枯渇によりFrontend経由の
   ライブE2E確認がまだできていない(6章1項と同じ制約)。

## 7. 次に進むために本当に必要なもの

* Gemini無料枠の日次クォータが枯渇しているため、クォータ回復後に
  以下のライブE2E確認を追加で行うことを推奨する:
  (a) `/converse`から実際にGeminiがupdateを選ぶこと(TD42)、
  (b) Frontend(`ConversationFlowScreen`)経由でHome画面から実際に
  Geminiとの会話でアプリが生成・更新されること(TD43)。
* Question Policy(design doc B.3の簡略版)の精度向上、Product Metrics
  計測基盤の設計は、いずれもCEO承認不要で次セッションから着手できる。
