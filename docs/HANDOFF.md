# Forge 申し送り（最新）

**最終更新: 2026-08-17 / branch `claude/forge-master-handoff-k46jns`**
**最新: TD69クローズ（Design Intent + Hero KPI）。CI結果待ち**

> このファイルは**毎回の作業のたびに上書き更新して push される**。
> パスは固定なので、`docs/HANDOFF.md` だけ見れば最新状況が分かる。
> 過去の詳細は `docs/reports/` と `CHANGELOG.md` に残る。

---

## 1. CEOへの依頼

### 🔴 依頼1: 2つ目のAI APIキーが必要です

**実測（これは確かなこと）**: Geminiの429の本文そのものです。

```
"quotaId"    : "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
"quotaValue" : 20
"retryDelay" : "39s"
```

* 観測した**1つのモデル**について、無料枠の上限が **20** だった
* `quotaId` は **Project × Model** の組で数えると示している
* **2026-08-17の動作検証だけで、実際にこの上限へ到達しました**

**推測（まだ確かめていないこと）**: 「3モデルだから合計60回」
「1日20アプリで止まる」は、上の1件から広げた推測です。他のモデルの
上限は測っていません。

> **訂正**: 前版で「枠は**鍵ごとに**独立」と書きましたが、`quotaId`は
> `PerProject`と言っているので、**単位はProjectである可能性が高い**です。
> 同じProjectで鍵を増やしても増えないかもしれません。実測と食い違う
> 書き方をしていました（ChatGPTの監査で指摘を受けて訂正）。

**確かなこと**: 検証作業だけで上限に達したので、実運用に足りていません。
そして**別のProviderなら別の枠**になります——これは単位がProjectでも
鍵でも成り立ちます。

**お願いしたいこと**: 以下のいずれかで無料APIキーを取得してください。

| 優先 | サービス | URL |
|---|---|---|
| 1 | **Groq** | https://console.groq.com |
| 2 | **Cerebras** | https://cloud.cerebras.ai |
| 3 | **OpenRouter** | https://openrouter.ai |

取得後は `backend/.env` に3行足すだけの想定です。

```
FORGE_GROQ_API_KEY=（取得した鍵）
FORGE_GROQ_BASE_URL=https://api.groq.com/openai/v1
FORGE_GROQ_MODEL=（コンソールに表示されるモデル名）
```

> **ただし「コード変更不要」とは言い切れません。** Groq等の実APIは
> 一度も呼んでいないので（鍵が無いため）、これは**設計上の想定であって
> 証明された事実ではありません**。実接続で構造化出力の形式差やエラー
> 本文の違いが出れば調整が要る可能性があります（TD67）。
> 前版で「コード変更は不要です」と断定していたのを訂正しました。

鍵を渡していただければ、設定して実機で通るところまで確認します。

参照: `TECH_DEBT.md` TD66 / TD67

---

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

## 2. 直近でやったこと

| | 内容 | commit |
|---|---|---|
| R0 | Experienceを本番から記録 | `d065f58` |
| R0.1 | AI連携の失敗を修正（実機 0/6 → 6/6） | `736a5cd` |
| 013 | Pre-R1 Integrity Gate | `cb37f8f` |
| 014 | R1入口 + Design Language V1 | `f53963a` |
| **今回** | **R1の残件2件を閉じた（TD69）** | このpush |

### 前回 NO-GO と書いた理由が、2つとも埋まりました

014の報告で「R1 = NO-GO（部分完了）」と書きました。理由は2件で、
その両方を今回閉じています。

**1. AIがDesign Roleを選ぶようになりました**

前回は語彙（33個の意味の言葉）を作っただけで、**AIには一度も聞いて
いませんでした**。出ていた意味は全部Forge側が構造から決めたもので、
「AIが意味を決める」のAI側が動いていませんでした。

今回、AIに**選ばせる**ようにしました。ただし聞き方を絞っています。

```
❌ 聞かない: 「文字サイズは何px？」「色は何番？」
✅ 聞く   : 「この画面は詰めて見せる？ゆったり見せる？」
            → density.compact / density.normal / density.relaxed の3択
```

**AIの答えは信用しません。** 3択の中に無い答え、別の軸の答え
（`metric.primary`は正しい言葉ですが「密度」の答えではありません）は
通さず、既定値に落とします。**落としたこと自体を記録します**
——「AIが選んだ」と「Forgeが埋めた」が混ざると、後で学習させるときに
嘘のデータになるからです。

AIを呼べなくても生成は成立します。Design Languageを入れたせいで
アプリが作れなくなるのは本末転倒なので。

**2. 「今月の残高」を一番大きく出せるようになりました**

前回、`metric.primary`（画面で一番重要な数値）という言葉を語彙へ
入れたのに、**それを表示できるWidgetがありませんでした**。
「今月の残高を目立たせて」と言われても出す先が無い状態でした。

`metric_view` を作りました。家計簿を作ると、一覧の**上**に合計が
大きく出ます。

* **一覧より上**に置きます — 下だと「一覧のおまけの合計」になります
* 記録が0件のとき **「0」とは書きません** — 「0円使った」と読めて
  しまうので、「まだ記録がありません」と出します
* 数値を持たないアプリ（習慣・日記）には**出しません** — 「習慣が
  3件」は一番大きく出す数字ではないので

> 前回「Widgetを増やすのは後の段階だから今回は足さない」と書きましたが、
> **その判断は間違いでした**と訂正します。言えるのに作れない言葉を
> 語彙に残す方が害が大きいです。

### 見た目は変わりましたか

**家計簿・在庫など「数値を扱うアプリ」は変わります。** 一覧の上に
大きな合計が出るようになりました。それ以外（習慣・日記・買い物リスト）
は、密度と面の扱いをAIが選ぶようになった分だけで、大きくは変わりません。

### 今回増えた宿題（正直に）

**Curatedのアプリでも、AIを1回呼ぶようになりました**（前は0回）。

Curatedは「速い・安定・無料」が取り柄だったので、これは損失です。
Geminiの枠は実測で**1日20回/Model**なので、1回増えると作れる回数が
そのまま減ります。

それでも入れたのは、Curatedだけ意味の選択から外すと、**一番よく使われる
経路でDesign Languageが効かない**からです（家計簿と日記が同じ密度に
なります）。直す案は3つ考えてあります（TD70）。

詳細: `docs/reports/FORGE-R1-HERO-METRIC-AND-DESIGN-INTENT-report.md`

## 3. 今の状態

```
backend/tests    1182 passed / 16 skipped   ← 実測
forge_ai/tests    521 passed                ← 実測
frontend          この環境にFlutter SDKが無く、今回は実行できていません
                  （新規テスト21件はCIで初めて走ります）
CI               このpushの結果待ち
```

> **正直に**: Flutter側（`metric_view`の描画）は**まだ一度も動かして
> いません**。コードとテストは書きましたが、確認はCIのfrontend jobに
> 委ねています。落ちたら直します。

| 機能 | 状態 |
|---|---|
| 自然言語 → アプリ生成 | 動作（実Geminiで確認済み） |
| 会話（/converse） | 動作 |
| AI Router / fallback | 動作。Provider内のモデル切替も動作 |
| Experience記録（AI呼び出し単位） | 動作 |
| Generation記録（生成物単位） | 動作（AIを呼ばないCurated生成も残る） |
| **AIがDesign Roleを選ぶ** | **動作**（2軸。軸ごとに検証し、外れたら既定値） |
| **Hero KPI（合計を大きく出す）** | **動作**（Python側は実測。Flutter描画はCI待ち） |
| Local AIの学習 | 未着手（記録は貯まるが、Dataset化もLoRAもまだ） |
| Knowledge / RAG | 未着手 |
| Widget | **20種（v1.11）** |

## 4. 次にやること

**R1の完了条件は埋まりました。** CIがgreenなら R1 = GO です。

1. **CIの結果を確認する**（Flutter側が初回実行。落ちていれば直す）
2. **TD70を直す** — Curatedが1回AIを呼ぶようになった件。軸の答えを
   キャッシュするのが第一候補（同じ依頼なら同じ選択になるはず）
3. **R2（Forge Knowledge / RAG）へ進む**

## 5. 未解決として抱えているもの

| # | 内容 | 参照 |
|---|---|---|
| 1 | Experience/Generationが永続化されない（再起動で消える） | TD41 / TD64 |
| 2 | `ABANDONED`（会話の放棄）を検出していない | TD64 |
| 3 | **`runtime_outcome`が常にUNKNOWN** — Flutterから結果が戻る経路が無い | TD65 |
| 4 | **生成物への「これで良い」をUIが聞いていない** — 閉ループの最重要の辺が細い | TD65 |
| 5 | Privacy Policy未完成 | TD60 |
| 6 | Gemini枠の合計値・単位が未検証 | TD66 |
| 7 | 第二Cloudが実API未検証 | TD67 |
| 8 | JWT検証が`NotImplementedError` | `core/security.py` |
| 9 | Local AI実モデル実行0回 | TD51 |
| 10 | ~~AIがDesign Roleを選んでいない~~ → **解消** | TD69 |
| 11 | ~~Hero KPI Widgetが無い~~ → **解消** | TD69 |
| 12 | UPDATE/Revision Evidenceは設計のみ（実装はR2） | TD68 |
| 13 | **CuratedがAIを1回呼ぶようになった**（前は0回） | TD70 |
| 14 | **Flutter側の`metric_view`が未実行**（当環境にSDK無し、CI待ち） | 本報告 §4 |

---

## 6. 詳しい報告

| 文書 | 内容 |
|---|---|
| `docs/reports/FORGE-R1-HERO-METRIC-AND-DESIGN-INTENT-report.md` | **最新**。Design Intent / Hero KPI / 配線破壊試験12件 |
| `docs/reports/FORGE-R1-DESIGN-LANGUAGE-014-report.md` | 014の全項目 |
| `docs/spec/DESIGN-LANGUAGE-V1.md` | Semantic Vocabulary 33 role |
| `docs/reports/FORGE-PRE-R1-INTEGRITY-GATE-013-report.md` | 013 |
| `docs/reports/FORGE-ROADMAP-R0-report.md` | R0 / CI / R0.1 |
| `docs/reports/FORGE-AI-FOUNDATION-011-report.md` | 011の7点への回答 |
| `docs/reports/FORGE-AI-FOUNDATION-010-report.md` | その前段 |
| `docs/PRODUCT-DIRECTION.md` | **最上位方針（変更不可）** |
| `docs/ROADMAP-TO-TARGET.md` | 完成図までの段取り |
| `CLAUDE.md` | AIエージェントの作業ルール |
| `CHANGELOG.md` | Taskごとの記録 |
| `TECH_DEBT.md` | 技術的負債 TD1〜TD70 |
