# Forge 申し送り（最新）

**最終更新: 2026-08-17 / branch `claude/forge-master-handoff-k46jns`**
**最新commit: `bc16fb9` / CI 全4 job green（run 32095320829）**

> このファイルは**毎回の作業のたびに上書き更新して push される**。
> パスは固定なので、`docs/HANDOFF.md` だけ見れば最新状況が分かる。
> 過去の詳細は `docs/reports/` と `CHANGELOG.md` に残る。

---

## 1. CEOへの依頼

### 🔴 依頼1: 受け取ったキーについて（**至急3点**）

2026-08-17、CEOから**OpenAIのAPIキー**をチャットで頂きました。
先に伝えるべきことが3つあります。

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
backend/tests    1182 passed / 16 skipped
forge_ai/tests    521 passed
frontend          flutter analyze 0件 / flutter test 通過 / build web 成功
CI               全4 job green（commit bc16fb9、run 32095320829）
                 backend 3.11 / 3.12 / backend-smoke(起動+CORS) / frontend
```

> Flutter側（`metric_view` の描画）は**この環境にSDKが無いため自分では
> 実行できず**、CIで確認しました。1回目は落ちています（原因と対処は
> 下の「CIで1回落ちた件」）。2回目で全green。

| 機能 | 状態 |
|---|---|
| 自然言語 → アプリ生成 | 動作（実Geminiで確認済み） |
| 会話（/converse） | 動作 |
| AI Router / fallback | 動作。Provider内のモデル切替も動作 |
| Experience記録（AI呼び出し単位） | 動作 |
| Generation記録（生成物単位） | 動作（AIを呼ばないCurated生成も残る） |
| **AIがDesign Roleを選ぶ** | **動作**（2軸。軸ごとに検証し、外れたら既定値） |
| **Hero KPI（合計を大きく出す）** | **動作**（Flutter描画までCIで確認済み） |
| Local AIの学習 | 未着手（記録は貯まるが、Dataset化もLoRAもまだ） |
| Knowledge / RAG | 未着手 |
| Widget | **20種（v1.11）** |

### CIで1回落ちた件（記録として残します）

1回目（`27b3597`）は frontend job が落ちました。backend 3ジョブは
通っています。

原因は `metric_view` の追加漏れが**テスト側にもう1箇所**あったこと
です。Widget種別を並べるswitchが本体とテストの2箇所にあり、本体だけ
直していました。**同じ場所で落ちたのは3回目**なので TD71 として登録
しました。

救いはあります。Dartの網羅性検査が効くので**黙って壊れることはなく、
必ずコンパイルエラーになります**。壊れたアプリが出る種類の失敗では
なく、CIを1往復無駄にする種類の失敗です。

2回目（`bc16fb9`）で全4 job green。

## 4. 次にやること

**R1の完了条件は埋まり、CIも全green です。R1 = GO と考えています。**

1. **TD70を直す** — Curatedが1回AIを呼ぶようになった件。軸の答えを
   キャッシュするのが第一候補（同じ依頼なら同じ選択になるはず）
2. **R2（Forge Knowledge / RAG）へ進む**

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
| 14 | Widget種別の網羅switchが2箇所にあり、追加のたびにCIが落ちる（3回目） | TD71 |

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
