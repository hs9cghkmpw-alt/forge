# Frozen Final Holdout — 暫定運用（Repository には**問題本体を置かない**）

**Status:** ACTIVE（2026-09-04、CEO 指示により確定）

---

## 0. 一番大事な訂正

前回の報告で「Frozen Final Holdout が無いため、どの Capability も
`99_PROVEN` へ到達できない」と書き、それを**開発の停止理由のように**扱った。
これは誤りである。CEO 指示により次のとおり分ける。

```text
Implementation blocker          ≠ Frozen Holdout
Final 99% certification blocker = Frozen Holdout
```

**Holdout が無いことは、Capability の実装・評価・改善を止める理由にならない。**
いまは Development / Validation / Regression Evidence で能力を上げ続ける。
Holdout は Release Candidate が近づいてから投入する。

同じ扱いを Human Panel にも適用する（`FORGE-HUMAN-PANEL-ACQUISITION-PLAN`）。
Human 0 人は Implementation blocker ではなく、最終認定の Operational Gap である。

---

## 1. 暫定運用

```text
Development（Dev / Validation / Regression で能力を上げる）
   ↓
RC Freeze（Release Candidate を凍結し、Git SHA を固定）
   ↓
Independent Holdout creation（**この時点で初めて問題を作る**）
   ↓
Hash / provenance を記録
   ↓
Final execution（凍結した RC に対して 1 回だけ走らせる）
   ↓
Result only persisted（**結果だけ** Repository へ残す）
```

### Repository へ置いてよいもの

| 置く | 置かない |
|---|---|
| Holdout specification（この文書） | **問題本体** |
| Requirement-family allocation（どの Family を Holdout へ割り当てるか） | 問題文・期待値 |
| Scoring contract（何を合格とするか） | 生成 seed |
| Runner（実行手順と入出力の形） | — |
| Result schema | — |
| Expected hash / provenance format | — |

**いま秘密の問題を用意する必要は無い。** RC Freeze 後に独立生成する。

---

## 2. Requirement Family の割り当て

分割は **Family 単位**で行う。同じ Family の言い換えが Development と Holdout の
両方に入ってはならない（入ると Holdout は「見たことのある問題」になる）。

| Set | 割合の目安 | 誰が見てよいか |
|---|---:|---|
| Development | 60% | 開発 Agent が自由に見る |
| Validation | 15% | 開発 Agent が見る。調整に使った回数を記録する |
| Regression | 15% | CI が回す。内容は固定 |
| **Frozen Final Holdout** | **10%** | **RC Freeze まで誰も作らない** |

割り当ては Family ID の hash で決め、**後から動かさない**
（`family_allocation.json` に記録し、変更は履歴に残す）。

---

## 3. Scoring Contract

Holdout の 1 件は次の形で採点する。**採点規則を後から変えない。**

```text
1 Episode に対して:
  - task_completed          : 利用者の目的が達成されたか（Oracle 判定）
  - required_semantics_kept : 必須意味が落ちていないか（Hard Gate）
  - hard_gate_violations    : Safety / Privacy / Data loss の違反数（0 でなければ FAIL）
  - primary_success         : Repair や Fallback 無しで通ったか
  - repair_attempts         : 何回直したか
  - fallback_used           : 代替実装へ落ちたか
  - latency_ms              : 所要時間
  - model_calls             : Model 呼び出し回数
```

合格判定は **Wilson 95% 信頼下限 >= 0.99**（`scripts/check_capability_matrix.py`
と同じ計算）。平均ではなく下限で見る。

---

## 4. Provenance

Holdout の実行結果には次を必ず付ける。**どれか欠けたら結果は無効。**

| 項目 | 意味 |
|---|---|
| `rc_git_sha` | 凍結した Release Candidate の SHA |
| `holdout_manifest_sha256` | 問題集合そのものの hash（中身は残さない） |
| `family_allocation_sha256` | 割り当て表の hash |
| `scoring_contract_version` | 採点規則の版 |
| `created_at` / `created_by` | いつ・誰が作ったか（開発 Agent であってはならない） |
| `executed_at` | 実行日時 |

`created_by` が開発 Agent なら、それは Holdout ではない。

---

## 5. Result schema

`docs/evidence/holdout/result_schema.json` に置く。結果だけを Repository へ残す。

---

## 6. いまやること / やらないこと

| いま | あとで（RC Freeze 後） |
|---|---|
| Dev / Validation / Regression で能力を上げる | Holdout 問題の独立生成 |
| Family 割り当て表を作る | Hash と provenance の記録 |
| Scoring contract を固定する | 1 回だけの Final execution |
| Runner と result schema を用意する | 結果の永続化 |

**「Holdout が無いので待つ」はしない。**
