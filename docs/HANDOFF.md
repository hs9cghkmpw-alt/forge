# Forge 申し送り（最新）

**最終更新: 2026-08-17 / branch `claude/forge-master-handoff-k46jns`**

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
| R0 | Experienceを本番の3経路から記録する | `d065f58` |
| 011 §7 | CI（GitHub Actions） | `32087d5` `d206ac9` |
| R0.1 | **AI連携の失敗を修正**（実機 0/6 → 6/6） | `736a5cd` |
| — | 文書の抜けを埋める | `508009c` |
| — | 報告をmdで残す運用を確立 | `02c559c` |
| **013** | **Pre-R1 Integrity Gate**（下記） | 最新 |

### 013 で直したこと

ChatGPTによる独立監査の指摘を、**そのまま肯定せず現HEADで再現してから**
扱いました。

* **§1 CORS** — 再現せず。ただしHTTP契約テストとCI smokeを追加
  （regexを壊すと3件落ちる = 懸念自体は正当だった）
* **§2 空env** — 再現。**報告より影響が広く**、`.env.example`をコピー
  すると**Forge全体が起動しない**状態だった。共通境界
  (`app/core/env_settings.py`)を作り、生の`float(os.environ...)`が
  再び現れたら落ちるsource scanも置いた
* **§3 TD65の事実関係** — 私の書き方が広すぎた。測り直して訂正
* **§4 Curated → 学習ループ** — `GenerationRecord`を設計・実装・配線
* **§5 TD66** — 実測 / 推論 / 未検証 を分離
* **§6 「コード変更不要」** — 断定を撤回（TD67）
* **§7 CI** — `flutter build web` と **backend smoke（起動+CORS）**を追加
* **§8 古い注記** — 「fastapiが無く一度も実行できていない」が5ファイルに
  残っていた。全て訂正

**Pre-R1 Gate: GO**（詳細は
`docs/reports/FORGE-PRE-R1-INTEGRITY-GATE-013-report.md`）

---

## 3. 今の状態

```
backend/tests    1118 passed / 16 skipped
forge_ai/tests    521 passed
frontend          476 passed / flutter analyze 0件（CIで確認）
CI               全4 job green（commit cb37f8f）
                 backend 3.11 / 3.12 / backend-smoke(起動+CORS) / frontend(build web含む)
```

| 機能 | 状態 |
|---|---|
| 自然言語 → アプリ生成 | 動作（実Geminiで確認済み） |
| 会話（/converse） | 動作 |
| AI Router / fallback | 動作。Provider内のモデル切替も動作 |
| Experience記録（AI呼び出し単位） | 動作 |
| **Generation記録（生成物単位）** | **動作**（AIを呼ばないCurated生成も残る） |
| Local AIの学習 | **未着手**（記録は貯まるが、Dataset化もLoRAもまだ） |
| Knowledge / RAG | 未着手 |
| Widget | 19種（v1.9） |

---

## 4. 次にやること

**R1 — Design Language を「AIが選ぶ語彙」として導入。**

`docs/ROADMAP-TO-TARGET.md` R1。Schema + Compiler + Validator + Runtime
+ Conversation まで通します（Tokenを実装しただけを完成扱いしない）。

設計の芯:

```
❌ AIが決める:  font-size 36px / #23D18B / padding 16
✅ AIが決める:  metric.primary / finance.income / surface.elevated
   Forgeが保証: それが実際に何pxで何色になるか
```

R1が入ると、013で作った`GenerationRecord.design_language_roles`が
初めて埋まります（今は空 = 語彙がまだ無いという事実）。

---

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

---

## 6. 詳しい報告

| 文書 | 内容 |
|---|---|
| `docs/reports/FORGE-PRE-R1-INTEGRITY-GATE-013-report.md` | **最新**。013の全項目 |
| `docs/reports/FORGE-ROADMAP-R0-report.md` | R0 / CI / R0.1 |
| `docs/reports/FORGE-AI-FOUNDATION-011-report.md` | 011の7点への回答 |
| `docs/reports/FORGE-AI-FOUNDATION-010-report.md` | その前段 |
| `docs/PRODUCT-DIRECTION.md` | **最上位方針（変更不可）** |
| `docs/ROADMAP-TO-TARGET.md` | 完成図までの段取り |
| `CLAUDE.md` | AIエージェントの作業ルール |
| `CHANGELOG.md` | Taskごとの記録 |
| `TECH_DEBT.md` | 技術的負債 TD1〜TD67 |
