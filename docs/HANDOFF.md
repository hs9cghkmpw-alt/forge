# Forge 申し送り（最新）

**最終更新: 2026-08-24 / branch `claude/forge-master-handoff-k46jns`**
**最新commit: 017A Learning Contract Hardening（A1/A2/A3/C/D）**
**次: commit E（Learning Event Foundation）→ commit F（Semantic Design Revision）**

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

### 進捗

| | 内容 | 状態 |
|---|---|---|
| A | MeasureSemantics消失修正 | ✅ `50b2c3d` |
| B | Feedback / Revision Foundation | ✅ `fe2664c` |
| A1 | Revision training provenance | ✅ `b61b36d` |
| A2 | Feedback Event + ID分離 | ✅ `d163e6f` |
| A3 | Learning Contract + Local Promotion Gate | ✅ `2db1fcd` |
| C | 残R1 Hardening | ✅ `a514a37` |
| D | R2 Forge Knowledge / RAG | ✅ `e40c861` |
| E | Growing AI Learning Event Foundation | ⬜ **次はここ** |
| F | Semantic Design Revision | ⬜ |

### 017AのReviewで指摘された4つの穴 — 全部塞いだ

CEOの指摘は**全て正しかった**。commit Bで作った契約には次があった。

1. **由来不明/Test DoubleのRevisionが教師データになっていた。**
   `source`を見ていなかったので、既定の`UNKNOWN`のまま「利用者が受け
   入れた」だけで正例になった。テストは`mock`で大量に走るので、
   **実運用よりテストの方が「正例」を多く生む**状態だった
2. **Feedbackの時系列を捨てていた。** 「最初は良いと言ったが使ってみたら
   直した」は、最初から`CORRECTED`だったものとまるで意味が違う
   （前者は「一見よく見えるが実際には外している」）
3. **失効するハンドルを系譜のIDにしていた。** しかもそれは持っている人が
   評価を書けるToken。Cloudへ載せると誰でも評価を書き換えられる
4. **内容ハッシュをClientへ返していた。** 同じ内容なら誰が作っても同じ値
   になるので、利用者を跨いだ突き合わせに使える

### Semantic Critic の誤検知2件（再現してから直した）

* 単一であるべきroleを**文書全体**で数えていた。別画面がそれぞれ主KPIを
  1つ持つ**正しい設計**が弾かれ、画面が増えるほど誤検知が増える形だった
* 家計簿は`finance.expense`（お金の向き）と`state.danger`（予算超過）を
  **正当に両方使う**。それを弾いていた

### Knowledgeが本番から呼ばれるようになった（TD69解消）

`knowledge_entries()`は014から存在したが、本番から1度も呼ばれていなかった。
`IntelligenceContextResolver`が**Provider選択の前に**解決し、
`GenerationRecord.knowledge_references`へ版付きで残るようになった。

`app_id`はコードに1箇所も無かった。**Knowledge型が最初の1箇所**である。

---

## 3. 今の状態

```
backend  : 1407 passed, 16 skipped
forge_ai :  521 passed
ruff（変更ファイル）: All checks passed
配線破壊試験: 24 round すべて確認
```

### 動くもの

* 会話 → ヒアリング → 生成 → Validator → Critic → Flutter描画
* Design Language 33 role・Semantic Design Critic（誤検知2件を修正）
* Provider Registry / AI Router / quota-aware fallback
* Generation / Experience / Revision / Benchmark Evidence
* `POST /api/v1/ai/feedback`（評価を書く唯一の口、時系列で残る）
* Forge Knowledge + Intelligence Context Resolver（本番から呼ばれる）
* Local Promotion Gate（**昇格0件。データ待ち**）

### まだ無いもの（正直に）

* **Flutter側の👍ボタン。** Backendの口は揃ったが、**利用者が押せる
  ボタンはまだ無い。** `user_acceptance`が実データで埋まるわけではない
* **Learning Eventを作って送る経路**（commit E）。語彙と契約はあるが、
  Eventを組み立てるコードは無い
* **Consent / Sanitizer / Retention / Dataset Lineage**（commit E）
* **`/update`から`RevisionRecord`を書く配線**（commit F）
* **実Local Modelでの生成は0回。** Provider抽象があることと、Localで
  実際に作れることは別である（Architectureの「Base Model = ✅」は
  過大評価だったので訂正した）

---

## 4. 次にやること

### commit E — Growing AI Learning Event Foundation

語彙（`LearningEventType` / `LearningTaskId` / scope 3軸）は入った。
次はEvent本体と、それに付く Consent / Sanitizer / Retention。

**決まっていること**（017A §11、判断F決着）:

```
Local Evidence      cross-session identityを持たない。いまのまま
      ↓ Consentを通ったEventだけ
Cloud Learning Event  pseudonymous contributor identity を持つ
```

ただし **client-generated install ID だけを Poisoning 防止の Truth に
しない**（端末側で作り直せる）。server-issued token が要る。
**IDを持っただけでSybil対策が済んだとは言わない。**

### commit F — Semantic Design Revision

「伝えたらデザインを直す」の本体。型（`RevisionRecord` /
`DesignRevision`）とStoreはできているので、`/update`から書く配線と
Semantic Patch（局所適用）を作る。

---

## 5. 未解決として抱えているもの

| 項目 | 状態 |
|---|---|
| OpenAI API鍵の失効（§1 依頼1） | **CEO対応待ち** |
| CORS障害が実際に起きているか（§1 依頼2） | CEO回答待ち |
| 仮名IDの発行主体（server-issued token） | 方針だけ決定。実装はE |
| `app_id`をClientから受ける経路 | **無い。** SDK公開前に必ず要る（017A §12） |
| 実Cloud Providerでの`/feedback`往復 | 未検証（実APIを呼んでいない） |
| Local Modelでの実生成 | **0回。未検証** |
| Flutter側の👍ボタン | 未実装 |

---

## 6. 詳しい報告

* `docs/reports/FORGE-017A-LEARNING-CONTRACT-HARDENING-report.md`（**今回**）
* `docs/architecture/FORGE-GROWING-AI-ARCHITECTURE.md`（**AI/Learningの正式Architecture**）
* `docs/reports/FORGE-017-ARCHITECTURE-REVIEW-report.md`（既存コードとの照合）
* `docs/spec/LEARNING-EVENT-V1.md`（契約のみ・未実装）
* `docs/reports/FORGE-016A-B-FEEDBACK-FOUNDATION-report.md`
* `docs/reports/FORGE-R1-CLOSURE-015-report.md`
* `docs/spec/DESIGN-REVISION-PROPOSAL.md`
* `docs/tasks/FORGE-016-STATE.md`
* `docs/API-KEY-TEST-GUIDE.md`
* `CHANGELOG.md` Task084 / Task085 / Task086
