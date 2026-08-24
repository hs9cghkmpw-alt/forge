# Forge 申し送り（最新）

**最終更新: 2026-08-24 / branch `claude/forge-master-handoff-k46jns`**
**最新commit: 016A commit B（Feedback / Revision Foundation）**
**進行中: FORGE-016A（A→B完了、C以降）+ FORGE-017 Growing AI Architecture（Review中）**

> このファイルは**毎回の作業のたびに上書き更新して push される**。
> パスは固定なので、`docs/HANDOFF.md` だけ見れば最新状況が分かる。
> 過去の詳細は `docs/reports/` と `CHANGELOG.md` に残る。

---

## 1. CEOへの依頼

### 🔴 依頼1: 受け取ったキーについて（**至急3点**）

2026-08-17、CEOから**OpenAIのAPIキー**をチャットで頂きました。
先に伝えるべきことが3つあります。

> **「どこかに使った？」への回答**: 使っていません。送信も0回です
> （接続の入口で遮断されたので、鍵はネットワークへ出ていません）。
> 検査結果と**試験のやり方**は
> **`docs/API-KEY-TEST-GUIDE.md`** にまとめました。

#### 1. このキーは失効させてください（至急）

**チャットに平文で流れたので、会話ログに残っています。**
Forgeのルール（`CLAUDE.md` §4「Git追跡対象に持ってよいのは環境変数の
名前だけ。値は持たない」）が守れる場所ではありません。

**私はこのキーをどこにも保存していません**（リポジトリにも、この
作業環境の`.env`にも書いていません）。それでも会話ログには残るので、
**OpenAIのコンソールで一度失効させ、新しい鍵を作り直してください。**
新しい鍵は、チャットではなく**CEOのPCの`backend/.env`へ直接**
書いてください。

#### 2. OpenAIのAPIには無料枠がありません

これは想定と違う可能性があります。お願いしていたのは
**Groq / Cerebras / OpenRouter の無料枠**でした。

OpenAIのAPIは**前払いのクレジット制**で、残高が無いと
`429 insufficient_quota` を返します。つまり、

* アカウントにクレジットが入っている → 使えます（**有料**）
* クレジットが無い → **1回も呼べません**

「Geminiの1日20回が足りない」という元の問題に対しては、
**有料での解決**になります。無料で枠を増やしたいのであれば、
Groq等の取得を別途お願いしたいです。どちらでも設定できます。

#### 3. この作業環境からは検証できませんでした

`api.openai.com` へ接続しようとしましたが、この開発セッションの
egressポリシーで遮断されました（`CONNECT tunnel failed, 403`）。
環境のドキュメントは「回避せず報告せよ」としているので、回避して
いません。

```
実施したこと : GET https://api.openai.com/v1/models
結果         : HTTP 000 / curl(56) CONNECT tunnel failed, response 403
意味         : キーが有効かどうかは**分かりません**（キーの問題では
               なく、ここから外へ出られないという問題）
```

**キーが生きているかの確認は、CEOのPCでしかできません。**

---

### ✅ 私の側で用意できたこと: コード変更なしで載ります

**追加の実装は要りませんでした。** 既にある「設定だけでProviderを
増やす口」がそのまま使えます。実際にlocalhostへ偽のOpenAI互換
サーバを立てて、**Forge側の配線が本当にHTTPを話せること**を
確認しました（`backend/tests/test_extra_cloud_provider.py`、7件）。

CEOのPCの `backend/.env` に、次の4行を足してください。

```
FORGE_EXTRA_PROVIDERS=openai_platform
FORGE_OPENAI_PLATFORM_BASE_URL=https://api.openai.com/v1
FORGE_OPENAI_PLATFORM_API_KEY=（新しく作り直した鍵）
FORGE_OPENAI_PLATFORM_MODEL=（コンソールで使えるモデル名。例: gpt-4o-mini）
```

> **`BASE_URL`と`MODEL`は私が確認したものではありません。** ここから
> OpenAIの公式ドキュメントへ到達できないため、記憶から書いています。
> **コンソールの表示で確かめてください。** 違っていれば、その2行を
> 直すだけです（コードは触りません）。

設定すると Auto Discovery が拾い、Geminiが枠切れのとき自動で
こちらへ回ります。`gemini`のような既存の名前は**上書きできない**
ようになっています（統計が混ざらないように）。

**検証区分**: Forge側の配線 = **実測（Test Double）** /
実際のOpenAI API = **未検証**。TD67は半分だけ解消です。

### 🟡 依頼2: 確認したいこと — CORS障害は実際に起きていますか

ChatGPTの監査で「localhost Originで既にCORS障害を踏んでいる」という
指摘を受けましたが、**私の環境では再現しませんでした。**

* 実コードのregexは正しい形（履歴を全部追っても壊れた版は存在しない）
* HTTPレベルで10 Origin叩いて、期待と1件も違わなかった

ただし**HTTPで確かめるテストが1つも無かった**のは事実なので、契約テスト
とCI smokeを追加しました（regexを壊すと実際に落ちます）。

**もしCEOの環境で実際にCORSエラーが出ているなら、原因は別にあります**
（proxy、ブラウザキャッシュ、`FORGE_ENV`がdevelopment以外、等）。
**その場合はブラウザのコンソールに出るエラー文をそのまま頂けますか。**

---

### ✅ 解決済み: Curated DomainとAIの関係（前版の依頼2）

前版は3択でCEO判断待ちにしていましたが、**第4の案を設計して実装しました。**

**AI呼び出しの記録**とは別に、**生成物の記録**(`GenerationRecord`)を
持つようにしました。`source = curated | cloud_ai | local_ai | ...` で
由来を区別するので、**AIを呼ばずに作った成功例も、同じ形の学習素材と
して並びます。**

Curatedを消さず、AIを無理に通さず、閉ループへ載せられました。
（学習データを作るためだけにCuratedへAIを通すのは本末転倒です——速くて
安定していて無料な経路を、記録の都合で遅く不安定に有料にすることに
なります。）

なお前版の「Curated DomainはAIを1回も呼ばない」は**測った範囲より広い
書き方**でした。会話そのものはAIを呼んでいます。訂正済みです。

---

## 2. いまの状況（2026-08-24）

### 直近のcommit

| 単位 | 内容 | 状態 |
|---|---|---|
| **A** | MeasureSemantics消失の実バグ修正（`FieldSpec`の`required`補正でmetadataが落ちていた） | ✅ push済み `50b2c3d` |
| **B** | Feedback / Revision Foundation | ✅ このpush |
| C | 残R1 Hardening（screen単位Critic / finance-state誤検知 / Golden Finance E2E） | 未着手 |
| D | R2 Forge Knowledge / RAG | 未着手 |
| E | Growing AI Learning Event Foundation（017） | Review中 |
| F | Semantic Design Revision | 未着手 |

### commit B で直した「本当に効いていなかったもの」

**「これでいい」をForgeが受け取る口が、本番に1本も無かった。**

`AcceptanceSignal`も`note_user_acceptance()`も011から実装済みだった。
013で`generation_ref`をPipelineから返すところまで直してあった。
**しかしHTTP層でそれが止まっていた**——`app/routers/`に`generation_ref`
の出現が0件、`note_user_acceptance`の本番呼び出しが0件。

結果、明示的な承認を要求する`is_positive_example`は**構造上、必ず
False**だった。「Local AIの教師データを貯める」と書いてある仕組みが、
貯める口を持っていなかった。

これは「作ったが本番から呼ばれない」の**5例目**である。

#### 入れたもの

* `POST /api/v1/ai/feedback` — 評価を書く**唯一の口**
* `result.artifact = {artifact_id, fingerprint}` を成功レスポンスへ
* `ArtifactRegistry` / `ArtifactFeedbackService` / `document_fingerprint()`
* `RevisionRecord` / `DesignRevision` / `RevisionEvidenceStore`（TD68の型）
* `DesignDecisionSource.USER_CORRECTION`（AIの成功例と混ぜない）

#### 忘れられない場所へ置いた

登録は`_result_dto()`の中に置いた。成功レスポンスの経路3つ
（`/generate`・`/generate/confirm`・`/converse` BUILD）が**全部ここを
通る**ので、4つ目の経路を足した人が呼び忘れても登録される。
呼び出し側3箇所に書く案は採らなかった——それが4回失敗した形である。

#### 配線破壊試験 6round（全て確認済み）

外すと落ちること、戻すと通ることを**実際に外して**確認した。
詳細は `docs/reports/FORGE-016A-B-FEEDBACK-FOUNDATION-report.md` §4。

---

## 3. 今の状態

```
backend  : 1304 passed, 16 skipped
forge_ai :  521 passed
ruff（変更ファイル）: All checks passed
```

### 動くもの

* 会話 →ヒアリング→ 生成 → Validator → Critic → Flutter描画
* Design Language 33 role・軸ごとの検証・Semantic Design Critic
* Provider Registry / AI Router / quota-aware fallback
* Generation Evidence（由来つき）・Experience Evidence
* **NEW** Artifact Feedback（`/feedback`）と Revision Evidence の型

### まだ無いもの（正直に）

* **Flutter側の👍ボタン。** Backendの口はできたが、**利用者が押せる
  ボタンはまだ無い。** 現時点で`user_acceptance`が実データで埋まる
  わけではない
* `/update`から`RevisionRecord`を書く配線（commit F）
* `ArtifactRegistry`の永続化（プロセス内メモリのみ、TD41と同じ制約）
* Forge Knowledge / RAG（commit D）

---

## 4. 次にやること

1. **FORGE-017 Architecture Review**（§27）——既存コードとの重複調査。
   新しい巨大parallel architectureを作らないことが目的
2. `docs/architecture/FORGE-GROWING-AI-ARCHITECTURE.md` を正式記録
3. commit C（残R1 Hardening）
4. commit D（R2 Forge Knowledge / RAG）

**017の型・境界（Learning Event Contract / scope / consent / provenance）は
C・Dを実装する時点から意識する。** 後から全面書き換えにしない（017 §24）。

---

## 5. 未解決として抱えているもの

| 項目 | 状態 |
|---|---|
| OpenAI API鍵の失効（§1 依頼1） | **CEO対応待ち** |
| 実Cloud Providerでの`/feedback`往復 | 未検証（実APIを呼んでいない） |
| CORS障害が実際に起きているか（§1 依頼2） | CEO回答待ち |
| `anonymous_user_id`の名称（017 §6） | 設計で再検討する |
| Personal / App / Global の境界の実装 | 017 E で扱う |

---

## 6. 詳しい報告

* `docs/reports/FORGE-016A-B-FEEDBACK-FOUNDATION-report.md`（今回）
* `docs/reports/FORGE-R1-CLOSURE-015-report.md`
* `docs/spec/DESIGN-REVISION-PROPOSAL.md`
* `docs/tasks/FORGE-016-STATE.md`
* `docs/API-KEY-TEST-GUIDE.md`
* `CHANGELOG.md` Task084
