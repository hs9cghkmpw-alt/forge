# 121 能力 Matrix と、99% を「作る」のではなく「証明する」ための仕組み

**Status:** ACTIVE（2026-09-03 新設）

**機械 Gate:** `python3 scripts/check_capability_matrix.py --summary`

---

## 0. この仕組みの大きさについて

指示 §9 の通り、**Evidence System を作るために Forge 開発が止まるのは禁止**
である。したがってここにあるのは 3 つだけである。

1. `capabilities.json` — 121 能力の状態台帳（1 ファイル）
2. `scripts/check_capability_matrix.py` — 台帳が身の丈以上を主張していないか
   だけを見る検査器（CI で走る）
3. この README — 数え方の規約

**評価 Platform は作っていない。** Capability-first → Proof Expansion に従い、
まず少数の代表 Capability で Implementation → Episode → Evidence →
Statistical Evaluation → Hard Gate → `99_PROVEN` を 1 本通し、それが機能して
から 121 へ横展開する。

---

## 1. Implementation Status の語彙

**下から順に厳しくなる。1 段飛ばして書かない。**

| Status | 意味 | 機械が要求するもの |
|---|---|---|
| `NOT_ASSESSED` | **この Task では見ていない。** 「無い」ではない | 実績値を入れてはならない |
| `NOT_STARTED` | 見た。実装が無いと確認した | — |
| `DESIGNED` | 設計だけある | — |
| `PARTIAL` | 一部だけ動く | `zero_budget_approach` |
| `IMPLEMENTED` | 本番経路に実物がある | 実在する `implementation_evidence` パス |
| `VERIFIED` | 実際に動かした Episode がある | `episodes >= 1` |
| `99_PROVEN` | Wilson 95% 下限が 0.99 以上 | `episodes >= 300` かつ下限 >= 0.99 |
| `HARD_GATE_PROVEN` | Hard Gate 項目で違反 0 件 | Hard Gate 項目であること |

`NOT_ASSESSED` と `NOT_STARTED` を分けているのは、**「見ていない」を
「無い」と書くのも嘘**だからである。121 のうち大半は前者である。

### 1.1 なぜ `99_PROVEN` に `episodes >= 300` を課すか

n=10 で 10 勝しても、Wilson 95% 信頼下限は **0.72** にしかならない。
「10 回中 10 回成功したので 100%」は 99% の証明ではない。
下限で 0.99 を超えるには数百件が要る。ここを緩めると、121 項目の合計は
意味を失う。

検査器はこの計算を**再実行して**、台帳の数字と一致するかを見る。
手で書いた下限は通らない。

---

## 2. Evidence Reuse Graph

121 能力 × 400 試験 = 48,400 を機械的に個別実行する設計にはしない。
1 つの Episode が複数の Capability を正当に証明できる場合、Evidence を
共有する。

### 2.1 形

```text
Requirement Family
  └─ Episode（1 回の実行。入力・経路・成果物・観測値の一式）
       ├─ proves → Capability            （複数可）
       ├─ under  → Target Contract       （その Capability の合格基準）
       └─ gates  → Hard Gate             （違反 0 が必要な条件）
```

`capabilities.json` の各項目は次を持つ。

```json
"evidence_reuse": { "episode_families": [], "shared_with": [] }
```

* `episode_families` — この Capability を証明している Requirement Family
* `shared_with` — 同じ Episode を根拠にしている他の Capability

### 2.2 共有してよい条件

1 つの Episode が Capability X と Y の両方を証明してよいのは、
**その Episode の中で X と Y の合格判定が独立に観測できる**ときだけである。

例：「鍵の持ち出しを記録する道具」を 1 回作り切った Episode は、

- GEN-01（会話→アプリ）を、利用者 Task 完遂の観測で
- GEN-03（Schema 正当性）を、Validator 通過の観測で
- GEN-07（CRUD）を、Create/Read/Update/Delete の実行で

それぞれ**別々に**証明できる。この 3 つは同じ Episode を共有してよい。

### 2.3 共有してはいけないもの（水増しの禁止）

> **同じ Requirement Family の言い換えを、独立試験として数えない。**

- 「家計簿を作りたい」「お金の管理をしたい」「収支を記録したい」は
  **1 Family**である。3 件と数えない。
- Family の同一性は**意味**で決める。文字列の差ではない。
- 独立 Episode 数の分母は Family 数であって、言い換え数ではない。

この規約を破ると、`episodes >= 300` は簡単に達成できてしまう。
達成できてしまう指標は指標ではない。

---

## 3. Dataset の分離（Frozen Final Holdout）

開発 Agent が何度も見た Benchmark を、最終 99% 証明に使ってはならない。

| Set | 誰が見てよいか | 用途 |
|---|---|---|
| **Development** | 開発 Agent が自由に見る | 実装中の反復 |
| **Validation** | 開発 Agent が見る。ただし調整の根拠にした回数を記録する | 手法選択 |
| **Regression** | CI が回す。内容は固定 | 退行検出 |
| **Frozen Final Holdout** | **開発 Agent から見えない** | 最終 99% 証明のみ |

### 3.1 Paraphrase Leakage の防止

分離は **Requirement Family 単位**で行う。同じ Family の言い換えが
Development と Holdout の両方に入ってはならない——入ると、Holdout は
「見たことのある問題」になる。

分割手順:

1. 要求を Family へ束ねる（意味で束ねる）
2. **Family 単位で** Development / Validation / Regression / Holdout へ割る
3. 割り当てを Family ID の hash で固定し、後から動かさない
4. 個々の言い換えは、所属 Family と同じ Set にしか入れない

### 3.2 Holdout を開発 Agent から隠す運用

**この Repository は開発 Agent が全部読める。** したがって Holdout の
中身を同じ Repository へ平文で置いた時点で、隠したことにならない。

採れる 0 円の手段は次のいずれかであり、**現時点ではどれも未実装**である。

| 手段 | 内容 | 状態 |
|---|---|---|
| H1 | Holdout を別 Repository（開発 Agent が access できない）に置き、CEO だけが実行する | 未実装 |
| H2 | Holdout の内容を CEO 手元にだけ置き、Repository には Family ID と結果だけを commit する | 未実装 |
| H3 | Holdout を生成規則ごと封じ、Seed を CEO が保持する | 未実装 |

**したがって現在、Frozen Final Holdout は存在しない。**
Z12 の 99% 証明は開始できない。これは実装の問題ではなく運用設計の問題で
あり、CEO の決定が要る（H1 / H2 / H3 のどれを採るか）。

---

## 4. 99% だけでは隠せない Outcome 指標

**Fallback 込みで 99% なら良い、にはしない。** 毎回 3 回 Repair して
数分かかるなら、2億円 Target との差 0 とは認定しない。

Episode は最低限これを記録する。

| 指標 | なぜ要るか |
|---|---|
| `primary_success` | 1 発で通ったか。Repair 前提の 99% と区別する |
| `repair_attempts` | 何回直したか |
| `fallback_rate` | 代替実装へ落ちた割合 |
| `latency_p50 / p95 / p99` | 平均だけ見ると尾が隠れる |
| `model_calls` | **決定的経路か Model 経路か**（`model_call_ledger.py`） |
| `actually_used_provider` | 呼んでいない Provider を書かない（TD104） |
| `peak_rss_mb` | 低資源端末で成立するか |
| `crash` | 落ちたか |
| `data_loss` | 利用者のデータを失ったか（Hard Gate） |
| `silent_failure` | 成功に見えて中身が欠けたか（Hard Gate） |

`model_calls` と `actually_used_provider` は
`backend/app/ai/gateway/model_call_ledger.py` が本番経路で記録している。
残りは**未収録**である。

---

## 5. いまの状態（2026-09-03）

`python3 scripts/check_capability_matrix.py --summary` の出力が正である。
この README に数字を焼き込まない（古くなるため）。

確かなことだけ書く。

- `99_PROVEN` は **0 件**
- `HARD_GATE_PROVEN` は **0 件**
- 大半は `NOT_ASSESSED`（見ていない）であり、`NOT_STARTED`（無い）ではない
- Frozen Final Holdout が無いため、最終証明は**開始できていない**

**「能力差 0 達成」「全体 99% 達成」と書ける状態ではない。**
