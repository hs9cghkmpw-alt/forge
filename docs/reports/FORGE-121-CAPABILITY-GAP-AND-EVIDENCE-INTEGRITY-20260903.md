# 121能力 Gap Matrix と、Evidence を信用できる形にする — 2026-09-03

**Base HEAD:** `61a199d66a991ab509aee982159df6c16ab42d68`

**Branch:** `claude/forge-master-handoff-k46jns`

---

## 0. まず、簡単な言葉で

今回やったことは 3 つある。

1. **「全部でいくつあって、いま何ができているのか」を 1 枚の表にした。**
   121 個の能力を機械が読める形（`capabilities.json`）にして、
   **できていないものを「できている」と書けないように検査器を付けた。**
   結果は正直に言うと、証明済み（99%）は **0 件**である。

2. **「勝手に外部の AI を呼んでしまう」穴を塞いだ。**
   前回、API キーが置いてあるだけで実 Gemini が呼ばれた。
   これからは、キーがあるだけでは呼ばない。呼ぶなら明示的に許可が要る。

3. **「呼んでいない AI の名前を記録に書く」問題を直した。**
   1 回も AI を呼んでいないのに「Gemini が答えた」と記録が残っていた。
   これからは、呼んだ回数と、実際に答えた相手を分けて記録する。

**まだ言えないこと**も先に書く。能力差 0 も、全体 99% も、達成していない。
証明する仕組みを作り始めたところである。

---

## 1. 評価軸（指示 §1）に沿った自己採点

| 軸 | 今回の答え |
|---|---|
| どの能力を前進させたか | SEC-06、QA-05、EXT-03/08/09（正確化）、AI-06（正確化）。加えて 121 全体の可視化 |
| 2億円 Target との差が縮んだか | **能力の差は縮んでいない。** 縮んだのは「差を測れない状態」である。Evidence 整合性は Target Contract の前提条件 |
| 0 円を維持したか | 維持。新規支出なし。外部 API 呼び出しも 0 件（Default Deny により構造的に 0） |
| 品質低下で差を隠していないか | 隠していない。むしろ EXT-08 を `NOT_STARTED` へ**下げた**（Sandbox が無いと確認したため） |
| 99% を証明する Evidence が増えたか | 直接の Episode は増えていない。**Evidence が嘘をつけない形になった**（TD104 / 外部通信 / Matrix 検査） |
| 別の Gap を作っていないか | §7 の Default Deny は Real Provider Test の手順を 1 つ増やした。手順は `.env` ではなく明示 flag に固定した |

---

## 2. 121能力 Implementation Gap Matrix（指示 §2）

### 2.1 場所

- 台帳: `docs/evidence/capability_matrix/capabilities.json`（121 件）
- 規約: `docs/evidence/capability_matrix/README.md`
- 検査器: `scripts/check_capability_matrix.py`（CI で実行）

Target Contract は戦略 §2.5 の表を**そのまま**取り込んだ（改変していない）。

### 2.2 状態集計（2026-09-03）

| Implementation Status | 件数 |
|---|---:|
| `NOT_ASSESSED`（今回見ていない） | 102 |
| `NOT_STARTED`（見た。実装が無い） | 2 |
| `PARTIAL` | 5 |
| `IMPLEMENTED` | 12 |
| `VERIFIED` | 0 |
| **`99_PROVEN`** | **0** |
| **`HARD_GATE_PROVEN`** | **0** |

Hard Gate 項目は 121 中 **23 件**。

### 2.3 `NOT_ASSESSED` を 102 件も残した理由

**121 能力を 1 セッションで正しく評価することはできない。**
できないものを「たぶん PARTIAL」で埋めると、表全体が推測になる。

`NOT_ASSESSED` は「無い」ではなく「見ていない」である。この 2 つを
分けたので、次のセッションは**どこから見ればよいかが分かる**。

### 2.4 検査器が防ぐこと（実際に壊して確認した）

| 壊し方 | 検出 |
|---|---|
| 1 回成功を `99_PROVEN` と書く | 検出（episodes=10 は最低 300 に足りない／Wilson 下限 0.72 < 0.99） |
| 根拠パス無しで `IMPLEMENTED` | 検出 |
| 存在しないパスを根拠にする | 検出 |
| Wilson 下限を手で盛る | 検出（再計算と不一致） |
| 動かさず `VERIFIED` | 検出（episodes=0） |
| 99% 項目に `HARD_GATE_PROVEN` | 検出 |
| 分母を 121→120 に減らす | 検出 |

7 件すべて検出。**置物ではない。**

---

## 3. Evidence Reuse Graph（指示 §3）

`docs/evidence/capability_matrix/README.md` §2 に規約を置いた。

- 1 Episode が複数 Capability を証明してよいのは、**その Episode の中で
  各 Capability の合否が独立に観測できる**ときだけ。
- **同じ Requirement Family の言い換えを独立試験として数えない。**
  分母は Family 数であって言い換え数ではない。

台帳の各項目に `evidence_reuse.episode_families` / `shared_with` を持たせた
（現在はすべて空。Episode をまだ紐付けていない）。

---

## 4. Gap の順位付け（指示 §4）

`Impact × Gap Size × Dependency × Evidence Leverage × Implementation Cost`
で並べた上位 10。**簡単な順ではなく、波及の大きい順**である。

| # | Gap | なぜ上位か |
|---|---|---|
| 1 | **Sandbox（EXT-08）** | 無いまま Self-Extension が動いている。EXT-03/09/10 と SEC 全体がここに依存 |
| 2 | **Frozen Final Holdout の運用** | 無いと、どの Capability も `99_PROVEN` へ到達できない。CEO 決定待ち |
| 3 | **Outcome 指標の Episode 収録**（Repair / p95 / RAM 等） | 99% の裏で性能が落ちていないことを示す唯一の手段（§11） |
| 4 | **Capability Tier のコード強制** | Tier C の無承認自動実行 0 件（Hard Gate）が現在成立していない |
| 5 | **Reuse の永続化（TD97）** | 再利用が process ローカル。EXT-11/14 が閉じない |
| 6 | **実 Local Model での閉ループ完走（EXT-14）** | 「実 Local Model が新 Capability を完走した回数 = 0」を 1 にする |
| 7 | **Permission Manifest（EXT-03 / T12）** | 生成 Tool の権限逸脱を検出できない |
| 8 | **BUILD 段の実時間測定（TD98）** | 速度が Target Contract の一部。未計測のまま 99% は言えない |
| 9 | **Human Panel H0（3〜5 人）** | Oracle の校正が始まらない。400 人の前に手順を作る |
| 10 | **依存 allowlist（T7）** | Supply chain。生成物が任意 package を引ける |

1 と 2 は**他の全部を止めている**。次のセッションはここから。

---

## 5. ADR-015: 生成 Source は Drift か Evolution か（指示 §5）

`docs/adr/ADR-015-generated-source-is-evolution-not-drift.md`

### 結論

> **意図的な Architecture Evolution である。ただし Gate は未完成。**

根拠:

- Constitution §8 が「controlled synthesis」を長期方向として明記している
- Constitution §10 が `build/test/runtime observations` と `promotion gates` を
  決定論側の責務として列挙している
- 2億円 Target 側から見て、GEN-09/10/11・EXT-04/06 は Typed IR の語彙だけでは
  満たせない。**能力を削って JSON-only を守るのは指示が禁止している**

### すでに閉じている Gate（実装確認済み）

隔離生成 / Digest 固定（検査した物 == 載せる物）/ 静的解析（`dart analyze`）/
生成テスト実行 / 実 Build / Runtime probe（loaded）/ Validator 語彙拡張の制限
（PROMOTED かつ loaded な BUILD_TIME のみ）/ 出荷物の空検査。

**「AI が書いた Source がそのまま Production へ入る」経路は現時点で無い。**

### まだ閉じていない Gate

**Sandbox・Permission Manifest・Capability Tier 強制・依存 allowlist の 4 つが無い。**
生成物の test/build を**ホスト権限**で実行している。

したがって EXT-08 を `NOT_STARTED` へ、EXT-03 と AI-06 を `PARTIAL` へ
**下げた**。ADR は「今の形が正しい」と言うためではなく、
**何が足りないかを固定するために**書いた。

---

## 6. TD104 — 呼んでいない Provider を記録しない（指示 §6）

### 何が壊れていたか

```python
provider_name = provider.last_provider_used or request.provider or "unknown"
```

`or request.provider` が問題。**1 回も Model を呼んでいないとき、
指定されただけの Provider 名**へ落ちる。指定は設定であって使った事実ではない。

`"unknown"` も問題で、「0 回呼んだ」と「呼んだが記録漏れ」を同じ語へ潰していた。

### 直し方

`backend/app/ai/gateway/model_call_ledger.py` を追加。

| 記録 | 内容 |
|---|---|
| `model_calls` | 試行の総数。**失敗した試行も 1 回**（呼んだのだから） |
| `actually_used_provider` | 実際に応答を返した Provider。0 回なら `None` |
| `configured_provider` | 指定された名前。**「使った」と読まない** |
| `deterministic_path` | Model を 1 回も呼ばずに答えたか |
| `fallback_used` | 別 Provider へ移ったか |
| `attempted_providers` / `failed_providers` | 何を試して何が落ちたか |

記録は `AIRouter._BoundAdapter.complete_structured`（**Model 呼び出しの唯一の口**）で
行う。呼び出し側が数える設計にしない——数え忘れた経路が「0 回」に見えると、
間違いが楽観側へ倒れる。

0 回のときの報告名は `"none"`。**Provider 名を作らない。**
HTTP 応答にも `attribution` として載る。

### 前回の観測についての訂正

前回 `provider: "gemini"` を観測したとき「fast path で LLM 0 回なのに Gemini を
名乗った」と書いた。**正確には、あの応答は BUILD/CONFIRM であり、会話段は
fast path（0 回）でも、そのあと Cognitive Pipeline が実際に Model を
呼んでいた**。したがってあの `"gemini"` 自体は誤りではなかった可能性が高い。

TD104 の本体は観測ではなくコードにある。`or request.provider` は、
**指定があって 0 回呼んだとき**に確実に嘘をつく。それを再現テストで示した
（`test_provider_attribution.py`）。

---

## 7. 実 Provider 誤爆を Architecture で禁止（指示 §7）

`backend/app/ai/gateway/external_call_policy.py`。**Default Deny。**

| 経路 | 既定 | 開ける条件 |
|---|---|---|
| Cloud Provider | **拒否** | `FORGE_ALLOW_REAL_PROVIDER_CALLS=1` を明示 |
| Cloud（テスト中） | **拒否** | 上記に加えて `FORGE_REAL_PROVIDER_TEST=1` |
| Local Provider | 許可 | 通常運用は環境変数不要（Local-first は製品の中核） |
| Local（テスト中） | **拒否** | `FORGE_REAL_PROVIDER_TEST=1` |

**API キーの存在を同意として扱わない。** これが 2026-09-02 の事故の形だった。

Fail closed:
`1/true/yes/on` 以外の値（`ture` のような typo を含む）は**すべて拒否**。

強制点は**実通信の直前**（`httpx.Client` を作る場所）。
`app/ai/foundation` に Policy を通さない `httpx.Client(` が増えたら、
`TestNoUnguardedEgressPointAppears` が名指しで落ちる——
「呼び出し側が忘れずに確認する」設計は忘れられるため。

---

## 8. Local AI の Quality-first（指示 §8）

再設計はしていない。**破られていないことを確認した。**

- `scripts/check_universal_quality_policy.py`: **PASS**
- `Low resource PC = Small Model` の再導入なし
- Hardware Profile を品質 Tier にする記述なし
- 今回追加した Default Deny は**Local を通常運用で妨げない**
  （妨げると「利用者に環境変数を触らせる」ことになり Universal Quality §9 違反）

---

## 9. 実行した検証

| 検証 | 結果 |
|---|---|
| `pytest backend/tests` | **2066 passed / 16 skipped**（前回 2035） |
| `pytest forge_ai/tests` | **747 passed / 10 skipped** |
| `flutter analyze --fatal-infos --fatal-warnings` | No issues found |
| `flutter test` | **589 passed** |
| `scripts/check_universal_quality_policy.py` | PASS |
| `scripts/check_capability_matrix.py` | PASS |
| Real Provider calls | **0 件**（Default Deny により構造的に 0） |
| Real Local Model runs | **0 回** |
| Human Evidence | **0 人** |

### 9.1 配線破壊試験

| 壊した箇所 | 結果 |
|---|---|
| Gemini の egress guard を削除 | 2 件 FAIL |
| OpenAI 互換 Adapter の egress guard を削除 | 2 件 FAIL |
| Adapter の `deployment` 既定を `"cloud"` → `"local"` | 1 件 FAIL |
| `attribution.reported_provider` を旧 `or request.provider` へ戻す | 2 件 FAIL |
| Router の `record_routed_result` を削除 | 1 件 FAIL |
| Matrix 検査器への 7 種の水増し | 7 件すべて検出 |

すべて復元して全 PASS を確認。

---

## 10. 未実証（達成済みと書かない）

| 項目 | 状態 |
|---|---|
| 121 能力の Target Contract 充足 | **0 件が `99_PROVEN`** |
| Frozen Final Holdout | **存在しない**。運用設計が未決（CEO 決定待ち） |
| Human Panel | **0 人**。H0（3〜5 人）も未実施 |
| Sandbox（EXT-08） | **未実装**。生成物をホスト権限で実行している |
| 実 Local Model の閉ループ完走 | **0 回** |
| Outcome 指標（Repair / p95 / RAM 等） | `model_calls` と `actually_used_provider` のみ収録。残りは未収録 |
| Security Corpus | **未定義**。`HARD_GATE_PROVEN` を名乗れる Security 項目は 0 件 |
| 実端末 Mobile / Tablet | 未確認 |

---

## 11. 新規 TECH_DEBT

| ID | 内容 |
|---|---|
| TD105 | 決定的経路（fast path）でも `bind()` が成功しないと会話が進まない。Model を 0 回しか呼ばない応答が Provider 可用性に依存している |
| TD106 | 会話段の内部例外が、すべて `ProviderError`（AI が使えない）として報告される。Forge 側の不具合が Provider の失敗として Evidence に残る |
| TD107 | Self-Extension に Sandbox が無い。生成物の test/build をホスト権限で実行している（ADR-015 §4.2、EXT-08） |
| TD108 | Capability Tier がコードで強制されていない。Tier C が Tier A と同じ経路を通れる |
| TD109 | Frozen Final Holdout の運用手段が無い。Repository が開発 Agent から全部読めるため、平文で置いた時点で Holdout にならない |

## 12. 解消 TECH_DEBT

| ID | 内容 |
|---|---|
| TD104 | 呼んでいない Provider の名前を Evidence が名乗る → 解消（§6） |

---

## 13. 攻撃的自己レビュー（指示 §15）

| 観点 | 疑い | 答え |
|---|---|---|
| Architecture | Default Deny が Local-first を壊さないか | 壊さない。通常運用の Local は環境変数不要。テスト中のみ拒否 |
| Semantic | 「決定的」と「模擬」を混同していないか | 分けた。`deterministic_path` と `simulated` は別フィールド |
| Security | Policy を外側から回避できないか | egress 直前で見ているので、Adapter を経由する限り回避不可。**ただし `app/ai/foundation` の外に新しい HTTP 経路を作れば回避できる**（検査器の走査範囲が `foundation` 配下だけ）。残存リスクとして記録する |
| Evidence integrity | Matrix 検査器自身が甘くないか | 7 種の水増しで検証。ただし**「内容が正しいか」は検査できない**（形式のみ） |
| Statistical validity | `episodes >= 300` は妥当か | Wilson 下限 0.99 を超えるのに必要な最小 n（全勝時）は約 300。全勝でない場合はさらに要る |
| Benchmark contamination | Holdout が無いのに Matrix を作った意味は | ある。**Holdout が無いことが可視化された**。以前は「無い」ことすら台帳に無かった |
| Zero-budget | 0 円を破っていないか | 破っていない。外部 API 呼び出し 0 件 |
| 2億円 Target parity | 差は縮んだか | **縮んでいない。** 縮んだのは測定可能性である。そう書いた |
| Maintainability | 121 件の JSON を人が保守できるか | 1 ファイル。検査器が形式を守る。Episode を紐付ける段で肥大化しないか要観察 |
| Future scalability | Episode が増えたとき台帳が破綻しないか | `evidence_reuse` は ID 参照のみ。Episode 本体は台帳に入れない設計にした |

### 13.1 この Task 自身の弱点

1. **102 件が `NOT_ASSESSED` のまま**である。表は作ったが、中身の大半は
   まだ調べていない。
2. **検査器は形式しか見ない。** `IMPLEMENTED` と書いてパスを添えれば通る。
   パスの中身が本当にその Capability を実装しているかは人が見るしかない。
3. **egress 検査器の走査範囲が `app/ai/foundation` 配下だけ**である。
   別の場所に HTTP 経路を作れば Default Deny を回避できる。
4. **Episode を 1 件も紐付けていない。** Evidence Reuse Graph は規約だけで、
   まだデータが無い。
