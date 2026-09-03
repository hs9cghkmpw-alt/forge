# ADR-015: 生成 Source は Architecture Drift ではなく、Gate 付きの Architecture Evolution である

**Status:** ACCEPTED（2026-09-03）

**Supersedes:** なし

**Relates to:** ADR-006（Provider Independence）、ADR-010〜012（Forge IR）、
Constitution §8 / §10 / §11、`docs/reports/FORGE-ZERO-BUDGET-ZERO-GAP-STRATEGY-20260902.md` §2.4

---

## 1. 判断を求められた問い

Forge の初期原則には、次の Trust Boundary がある。

```text
Natural Language → AI → JSON Schema → Validator → Flutter Renderer
```

**AI が出してよいのは JSON だけ**であり、実行される Dart は Forge が書いた
ものだけ、という境界である。

一方、現在の Repository には Self-Extension があり、**AI が Dart Source を
生成し、Build し、Forge 本体の Flutter アプリへ install する**経路が実在する
（`forge_ai/core/orchestration/synthesizing_build_time_implementer.py`、
`flutter_capability_installer.py`）。

これは意図的な進化なのか、それとも気付かないうちに境界が崩れた Drift なのか。

---

## 2. 決定

> **意図的な Architecture Evolution である。ただし「Source 生成が存在してよい」
> という意味であって、「AI の出力が Production へ入ってよい」という意味では
> ない。**

Typed IR を主経路として維持し、Source 生成は**それでは届かない Capability に
限った副経路**とする。副経路は Gate 列を全部通ったものだけが Production へ
入る。

---

## 3. なぜ Drift ではないと判断したか

### 3.1 Constitution が Source 生成を予定している

§8「Templates and widgets are primitives, not the boundary of generative power」
は、能力が足りないときの長期方向をこう書いている。

> capability decomposition, controlled synthesis, verification, reuse, and
> evidence-backed promotion

**controlled synthesis（管理された合成）** が明記されている。JSON だけで
到達できない Capability に対し、合成を禁じてはいない。禁じているのは
「widget/template が無いことを最終的な断り文句にすること」である。

### 3.2 Constitution §10 が役割分担を決めている

> AI decides meaning; Forge guarantees what can be guaranteed deterministically.
> ... schema validity, state consistency, permissions, atomicity, bounded tool
> access, validator rules, **build/test/runtime observations**, security
> constraints, **evidence integrity**, and **promotion gates**.

`build/test/runtime observations` と `promotion gates` が決定論側に列挙されて
いる。**Build と Promotion を通す設計そのものが Constitution の想定である。**

### 3.3 2億円 Target 側から見ても、JSON only では届かない

121 能力のうち、次は Typed IR の語彙だけでは満たせない。

| ID | 能力 | JSON only で届かない理由 |
|---|---|---|
| GEN-09 | 特殊 UI | Template なしの Encoding / View / Interaction。既存 widget 語彙の外 |
| GEN-10 | ゲーム | Loop / Rule / Collision / State は宣言的 UI 記述の外側にある |
| GEN-11 | インタラクティブ UI | Drag / Animation / Realtime は宣言では表現しきれない |
| EXT-04 | コード生成 | 定義上 Source を書く能力である |
| EXT-06 | Flutter Runtime 登録 | 新しい型を Runtime へ載せる |

指示にある通り、**能力を削って JSON-only を守るのは禁止**である。
したがって「JSON only へ戻す」は選べない。

---

## 4. しかし、いまの形が正しいという意味でもない

Drift ではないことと、Gate が十分であることは別である。現状を並べる。

### 4.1 すでに閉じている Gate

| Gate | 実装 | 何を防ぐか |
|---|---|---|
| 隔離生成 | `build_time_workspace.py` | 生成物を本体へ直接書かない |
| Digest 固定 | `VerifiedCapabilityArtifact`（`synthesizing_build_time_implementer.py`） | **検査した成果物と install する成果物が 1 byte でも違えば拒否** |
| 静的解析 | build plan の `dart analyze` step | 構文・型・lint |
| 生成テスト実行 | build plan の `dart run capability_test.dart` | 生成物が自分のテストを通ること |
| 実 Build | build plan の build step | 「書けた」と「載る」を分ける |
| Runtime probe | `extension_activation.py` の loaded 判定 | Build 成功と実際に載ったことを分ける |
| Validator 語彙拡張の制限 | `runtime_attested_widgets.py` | **PROMOTED かつ loaded な BUILD_TIME activation** のときだけ Validator の widget 語彙が広がる。宣言だけでは広がらない |
| 出荷物の空検査 | `test_shipped_acquired_registrations.py` | 獲得物を出荷物へ紛れ込ませない |

**「AI が書いた Source がそのまま Production へ入る」経路は、現時点で存在
しない。** Digest 一致・Build 成功・Runtime loaded・PROMOTED の 4 つを
同時に満たさないと Validator すら広がらない。

### 4.2 まだ閉じていない Gate

| 欠けている Gate | 現状 | 危険 |
|---|---|---|
| **Sandbox 実行** | 無い（`forge_ai/core` に sandbox 実装が存在しない） | 生成物の test/build を**ホストの権限**で実行している。EXT-08「Network/File/Process/Secret escape 0 件」は**未実装**であり、未検証である |
| **Permission Manifest** | 無い | EXT-03 が要求する Typed Contract + Permission Manifest のうち Permission 側が無い |
| **Capability Tier の強制** | 分類は策定済み（戦略 §2.4）だが、コードが Tier を強制していない | Tier C（Network / Credential / OS / 決済等）が Tier A と同じ経路を通れる |
| **供給元の固定** | 生成 Source の provenance は digest で追えるが、依存の allowlist が無い | 生成物が任意の package を要求できる |

**したがって現在の正しい表現は「Gate 付き Evolution だが、Gate は未完成」で
ある。** EXT-08 を `IMPLEMENTED` と書いてはならない。

---

## 5. 採用する Architecture

```text
Natural Language
  → Semantic IR (JSON)
  → Capability Plan (JSON)
  → Typed Forge IR (JSON)
  → Validator
  → Deterministic Compiler
  → Artifact
  → Runtime                                   ← ここまでが主経路
```

主経路で満たせない Need のときだけ、副経路へ落ちる。

```text
  Capability Gap
   → Extension Route 判定（Tier A / B / C）
   → 隔離生成（本体から切り離した workspace）
   → 静的解析
   → **Sandbox**（Network/File/Process/Secret を落とした実行）   ← 未実装
   → **Permission 判定**（Manifest と Tier に基づく）             ← 未実装
   → Build
   → Runtime probe（loaded か）
   → Digest 検証（検査した物 == 載せる物）
   → Promotion（Evidence Gate）
   → Runtime
```

### 5.1 不変条件

1. **AI の出力が、上記 Gate 列を通らずに Production の実行経路へ入ってはならない。**
2. Gate を 1 つでも飛ばした Artifact は Promotion 不可。
3. Validator の語彙は、**実際に載った Runtime** によってのみ広がる（実装済み）。
4. Tier C は無承認自動実行 0 件。人間の承認を Gate に含める。
5. 主経路で満たせる Need を、副経路へ流さない（Reuse-first が先）。

### 5.2 「JSON only へ戻す」を選ばなかった理由の要約

能力（GEN-09/10/11、EXT-04/06）を削ることになるため。指示の禁止事項
「能力を削って JSON-only を守る」に当たる。

### 5.3 「Gate 無しの Source 生成」を選ばなかった理由

Constitution §10・§11、および 2億円 Target の Hard Gate（EXT-08 は
「Network/File/Process/Secret escape 0 件」）に反するため。

---

## 6. この ADR が生む Work

| # | 内容 | 対応 Capability |
|---|---|---|
| W1 | Sandbox 実行（Network/File/Process/Secret を落として生成物の test/build を走らせる） | EXT-08、SEC 系 |
| W2 | Permission Manifest を Typed Contract の一部として必須化 | EXT-03 |
| W3 | Capability Tier をコードで強制し、Tier C を人間承認 Gate へ落とす | 戦略 §2.4 |
| W4 | 生成物の依存 allowlist | Supply chain |
| W5 | Gate を 1 つずつ外すと Promotion が落ちることの配線破壊試験 | EXT-10 |

W1〜W5 が閉じるまで、EXT-08 / EXT-03 / EXT-09 / EXT-10 を `VERIFIED` 以上と
書いてはならない。

---

## 7. 却下した代替案

| 案 | 却下理由 |
|---|---|
| JSON only へ戻す | GEN-09/10/11、EXT-04/06 を落とす。**能力を削って安全を主張することになる** |
| Source 生成を無制限に許す | Constitution §10・§11 と EXT-08 Hard Gate に反する |
| Source 生成を「開発者だけの機能」にする | 利用者の Need から Capability が生まれる閉ループ（Constitution §8）が切れる |
| Sandbox が無いまま Tier B を自動化 | 現在まさにこの状態であり、**それを是認しない**ために本 ADR を書いた |

---

## 8. 検証方法

- Gate 列の各段について、**外すと Promotion が落ちる**ことを配線破壊試験で示す。
- `runtime_attested_widgets.py` の 4 条件は既に破壊試験済み
  （`backend/tests/test_forge_020f_runtime_attested_widgets.py`）。
- Sandbox（W1）は、escape を試みる Corpus に対して 0 件を示すまで
  `NOT_STARTED` のままにする。**設計だけで status を上げない。**
