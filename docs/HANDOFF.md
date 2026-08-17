# Forge 申し送り（最新）

**最終更新: 2026-08-17 / branch `claude/forge-master-handoff-k46jns`**

> このファイルは**毎回の作業のたびに上書き更新して push される**。
> パスは固定なので、`docs/HANDOFF.md` だけ見れば最新状況が分かる。
> 過去の詳細は `docs/reports/` と `CHANGELOG.md` に残る。

---

## 1. CEOへの依頼（対応が要るもの）

### 🔴 依頼1: 2つ目のAI APIキーが必要です

**現状**: Gemini無料枠を実測したところ **1モデルあたり1日20回**でした。

```
"quotaId"    : "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
"quotaValue" : 20
```

Forgeは現在3モデルを使い分けるので **合計1日60回**が上限。
アプリ1個の生成で数回使うため、**1日20個ほど作ると止まります。**
2026-08-17の動作検証だけで使い切りました。

**なぜモデルを増やしても解決しないか**: 枠は**鍵ごとに独立**しています。
同じ鍵の中でモデルを増やしても20→60になるだけで、桁が変わりません。
**Providerを増やす以外に方法がありません。**

**お願いしたいこと**: 以下のいずれかで無料APIキーを取得してください。

| 優先 | サービス | URL | 備考 |
|---|---|---|---|
| 1 | **Groq** | https://console.groq.com | 無料枠が広い。OpenAI互換 |
| 2 | **Cerebras** | https://cloud.cerebras.ai | 同上 |
| 3 | **OpenRouter** | https://openrouter.ai | 無料モデルあり。同上 |

**コード変更は不要です。** Adapterは実装済みなので、`backend/.env` に
3行足すだけで動きます。

```
FORGE_GROQ_API_KEY=（取得した鍵）
FORGE_GROQ_BASE_URL=https://api.groq.com/openai/v1
FORGE_GROQ_MODEL=（コンソールに表示されるモデル名）
```

鍵を渡していただければ、設定して実機で通るところまで確認します。

参照: `TECH_DEBT.md` TD66

---

### 🟡 依頼2: 判断が要る — Curated DomainとAIの関係

**実測した事実**: 「家計の支出をカテゴリ別に管理したい」を投げると、
**0.01秒・AI呼び出し0件**で、Validator合格の完全なアプリが返ります。

Curated Domain Library（家計簿・釣り記録・習慣管理など）に載っている
ドメインは**完全にルールベースで生成**され、AIが動くのは
**Curatedに無いドメインのときだけ**です。

**なぜ報告するか**:

* Product Direction §4「有限Template選択システムへの退化は禁止」に
  触れる形に見える
* 一方、この経路は速く・安定し・品質も一定なので、**単純に消すのは
  明らかな後退**
* **Local AIへの影響が大きい** — この経路はExperienceを1件も残さない
  ため、**よく使われるドメインほど学習素材が集まらない**

**選択肢（未決定・CEOの判断待ち）**:

1. Curatedを**叩き台**にし、AIが利用者の言葉に合わせて調整する
   （安定と適応の両立。Evidenceも残る）
2. そのままにし、Curatedを「品質の下限保証」と位置付け直す
   （その場合 §4 との整合を文書で取る必要がある）
3. R1（Design Language）が入った時点で一緒に見直す

ロードマップの他のPhaseはこの判断に依存しないので、**返事を待たずに
先へ進めます。**

参照: `TECH_DEBT.md` TD65 / `docs/ROADMAP-TO-TARGET.md` R2.5

---

## 2. 直近でやったこと

| | 内容 | commit |
|---|---|---|
| R0 | Experienceを本番の3経路から記録する | `d065f58` |
| 011 §7 | CI（GitHub Actions） | `32087d5` `d206ac9` |
| R0.1 | **AI連携の失敗を修正**（実機 0/6 → 6/6） | `736a5cd` |
| — | 文書の抜けを埋める | `508009c` |

### R0 — Experienceを本番から記録する

Product Direction §7 が「完成扱いしてはならない」と名指しした状態
（ExperienceStoreはあるがProductionから記録されない）を解消。
Widget追加は0件。

記録地点を `AIRouter.generate()` — 本番のAI呼び出しが必ず通る唯一の
入口 — に置いたので、Endpointが増えても書き忘れられない。
Validatorの合否と利用者の承認/訂正は、後から書き足す形。

### R0.1 — AI連携の失敗を修正

**CEOが実機で踏んだ失敗。再現したら6回中6回失敗していた。**
原因は3つ重なっていた。

1. 既定モデル `gemini-flash-latest` が混雑して503（同時刻の実測で
   `gemini-flash-lite-latest` は3/3成功）
2. 「同じProviderを二度試さない」を**一時的な失敗にも**当てていた
3. `models` 宣言がRoutingに使われていなかった

Provider内でモデルを切り替える形にした（**Provider Identityは
増やしていない** — 011 §1の原則を守るため）。

### CI

`.github/workflows/ci.yml`。3ジョブとも green。**実APIは呼ばない**
（CIにAPIキーを置かない）。

---

## 3. 今の状態

```
backend/tests    1079 passed / 16 skipped
forge_ai/tests    521 passed
frontend          476 passed / flutter analyze 0件
CI               3ジョブとも green
```

| 機能 | 状態 |
|---|---|
| 自然言語 → アプリ生成 | 動作（実Geminiで確認済み） |
| 会話（/converse） | 動作 |
| AI Router / fallback | 動作。Provider内のモデル切替も動作 |
| Experience記録 | **動作**（R0で本番接続） |
| Local AIの学習 | **未着手**（記録は始まったが、Dataset化もLoRAもまだ） |
| Knowledge / RAG | 未着手 |
| Widget | 19種（v1.9） |

---

## 4. 次にやること

`docs/ROADMAP-TO-TARGET.md` の順に進めます。

* **R1** — Design Language を「AIが選ぶ語彙」として導入
  （Schema + Compiler + Validator + Runtime + Conversation まで通す）
* R2 — Forge Knowledge / RAG（Local AI優先順位 #1）
* R2.5 — Curated Domainの判断（上記 依頼2）
* R3 — 小さいWidget 4つ + Compiler接続

---

## 5. 未解決として抱えているもの

| # | 内容 | 参照 |
|---|---|---|
| 1 | Experienceが永続化されない（プロセス内メモリ、再起動で消える） | TD41 / TD64 |
| 2 | `ABANDONED`（会話の放棄）を検出していないので負例が偏る | TD64 |
| 3 | Privacy Policyが未完成 | TD60 |
| 4 | Curated経路からEvidenceが出ない | TD65 |
| 5 | 無料枠が足りない | TD66 |
| 6 | Local AIの実モデル実行が0回（環境制約） | TD51 |

---

## 6. 詳しい報告

| 文書 | 内容 |
|---|---|
| `docs/reports/FORGE-ROADMAP-R0-report.md` | R0 / CI / R0.1 の詳細 |
| `docs/reports/FORGE-AI-FOUNDATION-011-report.md` | 011の7点への回答 |
| `docs/reports/FORGE-AI-FOUNDATION-010-report.md` | その前段 |
| `docs/PRODUCT-DIRECTION.md` | **最上位方針（変更不可）** |
| `docs/ROADMAP-TO-TARGET.md` | 完成図までの段取り |
| `CHANGELOG.md` | Taskごとの記録 |
| `TECH_DEBT.md` | 技術的負債 TD1〜TD66 |
