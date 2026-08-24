# Forge 申し送り（最新）

**最終更新: 2026-08-18 / branch `claude/forge-master-handoff-k46jns`**
**最新commit: `c78c3be` / R1完了時（`a90d850`）から実装は入っていない**
**R1 DESIGN LANGUAGE = GO / 次の方針を設計中（実装前）**

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

## 2. いまの状況（2026-08-18）

### 方針が変わりました

CEOから**最優先方針**が来ています。

> **ユーザーが見た画面に対して普通の日本語で指摘すると、
> その意図を理解してデザインを直せること**

```
「残高をもっと目立たせて」   「一覧がごちゃごちゃしてる」
「このカードだけ目立たせて」 「赤が強すぎる」
「追加ボタンが目立ちすぎる」 「もっとシンプルにして」
```

対象は最終的に7分類すべて。優先順位は
**①情報階層・強調 → ②レイアウト/余白/密度 → ③コンポーネントの見せ方
→ ④Semantic Color/Theme → ⑤タイポグラフィ → ⑥細かな装飾
→ ⑦アニメーション・遷移**。

**これは見た目の便利機能ではありません。**

```
User Correction → Revision Evidence → Forge Knowledge → Local AI Improvement
```

を閉じる経路として設計します。閉ループの最重要の辺（TD65）が
ここで初めて繋がります。

### いま何をしたか

**設計案だけ作りました。実装は1行も入れていません**（CEO指示）。

| 文書 | 内容 |
|---|---|
| `docs/spec/DESIGN-REVISION-PROPOSAL.md` | 「見て、言って、直る」の設計案 |
| `docs/tasks/FORGE-016-STATE.md` | 016を完了可能な7単位へ分割 |
| `docs/OPEN-DECISIONS.md` | 判断待ち・制約・技術的負債 |

### 調べて分かったこと — 土台はかなり揃っている

推測せず実コードを読んで確認しました。

| 既にあるもの | 効き方 |
|---|---|
| **widget単位のrole適用**（`screen.styleRoles[node.id]`） | **「このカードだけ」が実現できる** |
| `RevisionRecord` の設計（TD68） | **型の設計は済んでいる**。実装が無いだけ |
| `classify_correction` の3段判定（態度→対比→対象） | 「違う」の解釈の土台 |
| `AcceptanceSignal`（ACCEPTED/CORRECTED/…） | 対を残す語彙 |
| `note_user_acceptance()` | 承認を書き足すAPI |
| Design Language 33 role・軸ごとの検証・Critic | 変更先の語彙と、直した結果の検査 |

### 見つかった致命的な欠け 2件

**1. `apply_update()` はデザインを知らない**

会話でアプリを直す経路はありますが、プロンプトに `style_role` も
Design Language も**一言も出てきません**（Widget型とstate型の話だけ）。
しかも変更要求と現在のJSON全部を渡して、**AIにJSON全体を書き直させて
います**。

「残高をもっと目立たせて」と言った結果、AIが支出のKPIを落としても、
**Validatorは構造しか見ないので通ります**。利用者は言っていないものを
失います。

**2. 承認を受けるHTTP口が1つも無い**

`note_user_acceptance()` は実装済みなのに、**それを呼ぶendpointが
存在しません**（grep済み）。Forgeが4回繰り返した
「作ったが本番から呼ばれない」の状態にあります。

### 一番大きな設計判断: 全体書き直しをやめる

AIに返させるのを **Document ではなく意味の変更指示** にします。

```
target : records_list_view    ← どのWidget
axis   : list_surface         ← どの軸
from   : surface.card         ← Forgeが埋める
to     : surface.elevated     ← AIが閉じた選択肢から選ぶ
```

Forgeがこれを**局所適用**します。触っていない場所は1バイトも
変わりません。

* 残高が消える事故が**構造的に**起きない（触らないから）
* 「何が嫌で、何をどう直したか」がそのまま記録になる
* AI呼び出しは1回（今のUPDATEと同じ。追加コストなし）

### なぜこのデータが価値を持つか

```
初回生成  surface.card
利用者    「もっと浮かせて」
修正      surface.elevated
利用者    「これでいい」

→ CORRECTED: surface.card    （外した選択）
→ ACCEPTED : surface.elevated （受け入れられた選択）
```

**この対は、完成Documentを何千個集めても得られません。**
Local AIが学ぶべきは「何が良いか」だけでなく、
「何を外したか」「どう直したら通ったか」だからです。

## 3. 今の状態

```
backend/tests    1258 passed / 16 skipped
forge_ai/tests    521 passed
frontend          508 passed / analyze 0件 / build web 成功
CI               全4 job green（commit a90d850）
```

**R1完了時（`a90d850`）から実装は増えていません。** 以降のcommitは
文書だけです。

> **016（P0バグ4件 + R2 Knowledge/RAG）は未着手です。**
> 押し忘れではなく、前回の応答が **API 529 Overloaded**（Anthropic側の
> サーバ混雑。一時的なもので、コードやリポジトリの問題ではありません）で
> 着手前に中断したためです。失われた作業はありません。

| 機能 | 状態 |
|---|---|
| 自然言語 → アプリ生成 | 動作（実Geminiで確認済み） |
| 会話（/converse） | 動作 |
| AIがDesign Roleを選ぶ | 動作（軸2つ。軸ごとに検証、外れたら既定値＋記録） |
| 数値の意味を判断する | 動作（評価は平均・サイズは最大・分からないなら出さない） |
| 収入/支出/残高 | 動作（単純合計を残高と呼ばない） |
| roleが見た目を変える | 動作（描画までCIで確認済み） |
| 良いDesignかの評価 | 動作（階層が壊れていればrelease_readyにしない） |
| **会話でデザインを直す** | **未実装**（設計案のみ。上記§2） |
| **利用者の承認を受け取る** | **未実装**（APIは在るが口が無い、TD65） |
| Knowledge / RAG | 未着手 |
| Local AIの学習 | 未着手 |
| Widget | 20種（Forge Language v1.12） |

## 4. 次にやること（CEO判断待ち）

### 提案する順番

```
016 単位1（MeasureSemantics消失バグ）   ← 先に潰すべき。修正は小さい
   ↓
R3-1 承認を受ける口                     ← 単独で閉ループが1本繋がる
   ↓
R3-2 RevisionRecord 実装（TD68の設計をそのまま使う）
   ↓
R3-3 Semantic Patch（局所適用）
   ↓
R3-4 優先1「情報階層・強調」の軸を追加
   ↓
R3-5 対象特定（AIにwidget idを選ばせる）
```

**なぜ単位1が先か**: AIが決めた「足せる量か」が保存時に消えるバグです
（`measure` がコピーされていない）。意味が消える状態のまま上へ機能を
積むと、後から原因が分からなくなります。

**なぜR3-1（承認の口）が次か**: それ単独で閉ループが1本繋がるからです。
「これでいい」を受け取れるようになるだけで、デザイン修正が1つも
実装されていなくても `ACCEPTED / CORRECTED` が貯まり始めます。

**016は捨てません。** P0の4件はどれもDesign Revisionの土台になります
（画面単位Critic＝直した結果の検査、finance誤判定＝「赤が強すぎる」の
扱い、/converse E2E＝Revisionも同じ道を通る）。

### 判断をお願いしたいこと

| # | 判断 | 影響 |
|---|---|---|
| 1 | **色をAIに触らせるか** | 案は「`#RRGGBB`ではなく、意味の色に `strong/normal/soft` の強度を持たせる」。触らせないなら優先④は後退します |
| 2 | **承認の口（R3-1）を先に単独で入れるか** | 入れると閉ループが1本繋がります |
| 3 | **対象特定をUIまで作るか** | AIにid を選ばせる方式だけなら、UI変更なしで始められます |
| 4 | **`latest` の意味**（下記§5） | 確定しないとKnowledgeへ書けません |

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
| 13 | **CuratedがAIを1回呼ぶ**（推奨解は記録済み） | TD70 |
| 14 | Widget種別の網羅switchが2箇所にあり、追加のたびにCIが落ちる（3回目） | TD71 |
| 15 | Live Testが廃止済みのprovider_idを見ていた（修正済み） | TD72 |
| 16 | **roleの反映はWidgetごとの対応が要る**（1箇所で被せれば効く、は成立しない） | TD73 |
| 17 | **Flutter側の配線破壊試験ができていない**（SDK無し） | TD74 |
| 18 | **`latest`の意味が曖昧** — 実装は「最後に追加した行」。「日付が一番新しい行」とは違う。確定しないとKnowledgeへ書けない | 016 §17 |
| 19 | **コントラスト比を測っていない** — 「Dark対応」と「読みやすさの保証」は別物 | 016 §18 |
| 20 | **`apply_update`がDesign Languageを知らない** — JSON全体を書き直させている | 設計案 §2 |
| 21 | **承認を受けるHTTP口が無い** — `note_user_acceptance`は実装済みなのに呼ぶ口が無い | TD65 |

---

## 6. 詳しい報告

| 文書 | 内容 |
|---|---|
| `docs/spec/DESIGN-REVISION-PROPOSAL.md` | **最新**。「伝えたら直る」の設計案 |
| `docs/tasks/FORGE-016-STATE.md` | 016の状態と、完了可能な7単位への分割 |
| `docs/OPEN-DECISIONS.md` | 判断待ち・制約・技術的負債の一覧 |
| `docs/reports/FORGE-R1-CLOSURE-015-report.md` | R1完了時の全項目・配線破壊試験・検証区分 |
| `docs/spec/METRIC-SEMANTICS-V1.md` | 数値が「どういう量か」の語彙 |
| `docs/API-KEY-TEST-GUIDE.md` | APIキーの扱いと試験手順（CEO向け） |
| `docs/reports/FORGE-R1-HERO-METRIC-AND-DESIGN-INTENT-report.md` | Design Intent / Hero KPI / 配線破壊試験12件 |
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
| `TECH_DEBT.md` | 技術的負債 TD1〜TD74 |
