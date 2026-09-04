# FORGE-PROMOTION-HARD-GATE-001 — Self-Extension Promotion 安全 Gate

**日付:** 2026-09-04 / **Status:** 実装完了・Episode 0 件

---

## 0. 簡単な言葉で

**AI が書いたコードを Forge 本体へ正式採用してよいかを、1 箇所でまとめて
判断するようにしました。**

これまでは「ビルドが通った」「テストが通った」で採用できました。
いまは、次のどれか 1 つでも欠ければ採用しません。

- どんな権限を使うのかの申告（**申告が無いなら「安全」ではなく「拒否」**）
- 危ないことをしていないか（ネット接続・秘密探し・外部コマンド実行など）
- どの檻の中で動かして確かめたか（**「檻なし」で確かめた結果は認めない**）
- 検査した物と載せる物が同一か（検査後のすり替え防止）
- 使っている部品が、Forge が素性を確かめた物だけか

そして**断った理由を必ず記録**します。「ダメでした」では後から調べられません。

---

## 1. Architecture の変更

### 1.1 判定を 1 箇所へ

```text
生成 Source
  ↓ 静的検査（Effect 抽出）        forge_ai/core/promotion/effects.py
  ↓ Sandbox 実行                   forge_ai/core/sandbox/（既存）
  ↓ 生成 test / build / probe      build_time_workspace（既存）
  ↓ ─────────── Promotion Gate ─────────  forge_ai/core/promotion/gate.py
  │   Permission Manifest / Tier / Effect / Secret /
  │   Dependency / Digest / Sandbox backend を 1 度に判定
  ↓ Registry 登録                  extension_registry（decision digest を検査）
  ↓ Reuse
```

### 1.2 忘れられない配線にした

このリポジトリは「作ったが本番から呼ばれない」を 10 回以上繰り返している。
したがって Gate は**呼ぶ側の善意に依存しない形**にした。

```python
def promoted(self, decision: PromotionDecision) -> "ExtensionManifest":
```

`decision` は**必須引数**である。Gate を通さずに Promotion しようとすると
`TypeError` で止まる。さらに:

| 迂回の試み | 何が止めるか |
|---|---|
| `promoted()` を引数なしで呼ぶ | `TypeError`（実行前に止まる） |
| 拒否された決定で呼ぶ | `PromotionDenied` |
| 他 Capability の決定を流用 | `ValueError`（identity 検査） |
| `replace(manifest, status=PROMOTED)` | Registry が `promotion_decision_digest` 空を拒否 |
| Store 経由で再読込 | Store が digest 無しを拒否 |

### 1.3 typed な拒否理由

`PromotionRejection` は 23 種の enum である。生の例外文字列で管理していない
ので、Evidence へそのまま載り、後から分類・集計できる。

---

## 2. 見つけた実バグ（設計の副産物）

Gate を配線したことで、**既存の穴が 5 件見えた**。

| # | 何が起きていたか | どう直したか |
|---|---|---|
| 1 | `sandbox_backend` が `BuildTimeBuildResult` に無く、**Promotion は policy-only と windows-appcontainer+job を区別できなかった** | backend を Promotion まで実際に流した |
| 2 | `CommandEvidence.os_isolated` が**定義されているだけで、どこからも呼ばれていなかった** | `ManagedBuildEvidence` で集約し Gate へ渡す |
| 3 | `os_isolated` の判定が 2 箇所にあり**内容が違った**（Gate は完全一致、CommandEvidence は前方一致）。`linux-namespace-fake` を OS 隔離と数えてしまう | 判定表を 1 つにした |
| 4 | 未知の Permission 値が混ざると `to_dict()` が**例外で落ち、typed 拒否を返す前に死ぬ** | 落ちずに拒否理由を返すよう修正 |
| 5 | Store が `promotion_decision_digest` を保存せず、**再読込で Gate 通過の証が消える** | 保存し、無ければ拒否 |

3 と 4 は**自分で Gate を攻撃して**見つけた（§5）。

### 2.1 自分の検査器のバグを 2 件

**1 件目（ローカルで発見）**

生成テストが隣の `capability_impl` を import するのを「未知の依存」と
誤検出した。**allowlist へ足して黙らせるのは誤り**なので、
「artifact の中に実在する module だけを内部扱いする」検査を足した。

**2 件目（CI が落ちて発見）** — 同じ直しを **Dart 側にしていなかった**。
`import 'capability_impl.dart';` を外部依存と誤検出し、
`test_dart_build_plan.py`（実 Dart を要する 4 件）が CI でだけ落ちた
（run `33864738810`）。**ローカルは Dart が無くて skip されるので気付けない。**

同じ取りこぼしを繰り返さないため、**Dart を必要としない形で本番 artifact の
import 構成を固定する回帰試験**を足した。以後は CI を待たずローカルで落ちる。

配線破壊で両方向を確認した。

```text
Dart 相対 import の内部判定を外す   → 2 件 FAIL（検出）
脱出 import（..）を内部扱いにする   → 1 件 FAIL（検出）
```

---

## 3. 実装したもの

| ファイル | 中身 |
|---|---|
| `forge_ai/core/promotion/effects.py` | Effect 抽出。Python は AST、Dart は構文走査。**言語別 Adapter + 共通 Policy** |
| `forge_ai/core/promotion/dependencies.py` | allowlist 突き合わせ。UNKNOWN Policy を明示的に分ける |
| `forge_ai/core/promotion/gate.py` | 判定本体。23 種の typed 拒否理由 |
| `forge_ai/data/generated_capability_dependencies.json` | 依存 22 件（実測。pubspec.lock と sandbox allowlist を読んで作成） |
| `scripts/promotion_mutation_runner.py` | Critical Gate 26 件の全数破壊試験 |
| `forge_ai/tests/test_promotion_gate.py` | 41 件 |
| `forge_ai/tests/test_generated_source_effect_corpus.py` | 危険 38 検体 + 誤検出 5 件 |
| `forge_ai/tests/test_promotion_gate_wiring.py` | 本番配線 6 件 |

### 3.1 「危険文字列があるか」にしていない

禁止語 list は語を避ければ抜ける。取っているのは **Effect（外界への作用）**である。

```text
Effect が宣言と食い違う → 拒否
Effect が読めない       → UNKNOWN → 拒否（fail closed）
```

`_INERT_SUFFIXES` に無い拡張子は**無害と仮定しない**。構文が壊れた Python も
UNKNOWN にする。

### 3.2 Dependency は宣言ではなく観測と突き合わせる

「依存を宣言してください」だけにすると、**宣言しなければ通る**。
突き合わせる相手は静的検査が実際に見つけた import である。

`security_status` は 22 件中 20 件が `UNKNOWN`。ネットワークへ出ないので
脆弱性情報を持てない。**UNKNOWN を安全扱いしていない**——`REJECT` と
`ALLOW_IF_BUNDLED` を明示的に分け、後者も「同梱済みで新規取得が発生しない」
ものに限る。

---

## 4. Mutation（実装要求 E）

**26 件の Critical Guard を 1 つずつ壊し、全件でテストが落ちることを確認した。**

```text
全 26 件の Guard が、壊すとテストで落ちる。
```

内訳（抜粋）: Permission Manifest 検査 / Tier 計算 / Human 承認 / 承認出所 /
Sandbox attestation / **policy-only を OS 隔離扱いにする改変** / 生成 test /
build / runtime probe / digest 一致 / digest 存在 / 禁止 Effect / 未宣言 Effect /
Secret / 権限昇格 / UNKNOWN の安全扱い / 構文破壊の安全扱い / 未知拡張子の
無害扱い / 静的検査必須 / 依存 allowlist / 依存 UNKNOWN / 依存取得行為 /
決定の必須性 / Registry の digest 検査。

### 4.1 「今回壊した分だけ分かる」からの脱却

以前は手で壊していたので**壊し忘れた Guard は永久に未検証**だった。
いまは一覧を持ち、**Gate を足して mutation を足し忘れると
`test_every_critical_gate_is_mutation_covered` が落ちる**。

この coverage 試験は導入直後に**実際に 1 件の穴を見つけた**
（`unknown_permission` に破壊試験が無かった）。

CI からも走る。

---

## 5. 自己批判レビュー（12 視点）

甘い自己評価をしないため、**設計後に自分で攻撃した**。

| 視点 | 見つけたこと | 対処 |
|---|---|---|
| Security | policy-only が本番証拠と混ざりうる | 判定表を 1 つにし、Evidence に `os_isolated` を常時記録 |
| Architecture | 判定が 2 箇所（Gate と CommandEvidence）にあった | 統合（§2 の 3） |
| Promotion bypass | `replace()` で PROMOTED を名乗れた | decision digest を Registry / Store が検査 |
| TOCTOU | 検証後のすり替え | source / artifact / manifest の digest を突き合わせ |
| Supply chain | 宣言だけなら空宣言で抜ける | 観測 import と突き合わせ |
| Permission escalation | 宣言より強い Effect | `_EFFECT_REQUIRES_PERMISSION` で検出 |
| Evidence integrity | 秘密の値が Evidence へ漏れうる | 値を書かず「secret-shaped」とだけ記録。試験で確認 |
| Cross-platform | Linux 前提になりうる | `windows-appcontainer+job` を OS 隔離として明示。試験あり |
| Test quality | 正常系だけ増える危険 | 正常系 4 件と拒否系 37 件を両方。**「全部落とす Gate」も害**として誤検出試験 5 件 |
| Mutation resistance | 一覧化しないと漏れる | coverage 試験で足し忘れを検出 |
| Performance | 生成物は小さく AST で十分 | 全 866 件 19 秒（悪化なし） |
| Maintainability | 拒否理由が文字列だと腐る | enum + `to_dict()` |

### 5.1 実際の攻撃結果

```text
攻撃1: 環境変数で policy-only を通す
  opt-in なし → 拒否
  opt-in あり → 通るが os_isolated=False（本番証拠と読めない）
  値が不正    → 拒否（"TRUE-ISH" では開かない）

攻撃2: backend 名を似せる
  'windows-appcontainer' / 'linux-namespace-fake' / 'policy-only '（末尾空白）
  / 'LINUX-NAMESPACE+PID' → **すべて拒否**

攻撃3: 難読化した危険コード
  'sub'+'process' の動的 import → dynamic_code として検出・拒否
  getattr(os, 'sys'+'tem')      → 検出・拒否（getattr を追加した）
  base64 に隠した eval          → 検出・拒否
```

攻撃 2 の `linux-namespace-fake` は、**修正前なら `CommandEvidence.os_isolated`
が True を返していた**。攻撃してみるまで気付いていなかった。

---

## 6. Acceptance Criteria

| 条件 | 結果 | 根拠 |
|---|---|---|
| Manifest 欠落で Promotion 不能 | ○ | `test_a_missing_manifest_refuses_promotion` |
| Unknown Permission で不能 | ○ | `test_an_unknown_permission_is_refused` |
| Tier C 無承認で不能 | ○ | `test_tier_c_without_human_approval_is_refused` |
| undeclared Effect で不能 | ○ | `test_an_undeclared_effect_refuses_promotion` |
| forbidden import / process / network で不能 | ○ | Corpus 38 検体、見逃し 0 |
| Secret 探索を検出 | ○ | `test_secret_hunting_is_reported_as_a_secret_violation` |
| Unknown dependency で不能 | ○ | `test_an_unlisted_dependency_refuses_promotion` |
| verified/promoted digest 不一致で不能 | ○ | TOCTOU 4 件 |
| Sandbox Evidence 欠落で不能 | ○ | `test_a_missing_backend_refuses_promotion` |
| test/build/probe 失敗で不能 | ○ | 3 件 |
| 正常 Tier A/B は可能 | ○ | 2 件 |
| 正常 Tier C + 承認は可能 | ○ | `test_tier_c_passes_only_with_approval_and_provenance` |
| 拒否理由が typed evidence に残る | ○ | `PromotionRejection` 23 種 |
| Critical Guard mutation 全検出 | ○ | **26/26** |
| 既存 Self-Extension regression を壊さない | ○ | forge_ai 866 / backend 2073 全通過 |
| Windows Sandbox を弱めていない | ○ | `windows_appcontainer.py` 未変更。OS 隔離として通す試験あり |
| policy-only を実 OS 隔離扱いしていない | ○ | `os_isolated=False` を試験で固定 |

---

## 7. 言えること / 言えないこと

### 言えること

- Promotion の判定点は**1 つ**になり、迂回は型・digest・Registry の 3 段で止まる
- Critical Guard 26 件は、**壊すと必ずテストが落ちる**（置物 0 件）
- 危険 Corpus 38 検体の**見逃し 0 件**
- policy-only は Evidence 上**永久に OS 隔離ではない**

### 言えないこと

- **「生成 Source は安全」とは言えない。** 静的検査は書かれたものしか見ない
- **Corpus は私が書いた。** 未知の書き方に対する見逃し率は**未測定**
- **Episode が 0 件。** 実際の獲得試行で Gate が何を通し何を止めたかの記録が無い
  （TD120）。したがって `VERIFIED` へは上げていない
- **重大脆弱 Dependency 0 件とは言えない。** 脆弱性情報を持っていない（TD113）
- **macOS は未実装**（TD117）
- `99_PROVEN` / `HARD_GATE_PROVEN` は **0 件のまま**

---

## 8. Capability Matrix

| ID | Before | After | 理由 |
|---|---|---|---|
| SEC-05 | PARTIAL | **IMPLEMENTED** | Effect 検査 + Corpus 見逃し 0。Episode 0 なので VERIFIED にしない |
| EXT-10 | IMPLEMENTED | IMPLEMENTED | Gate へ統合したが Episode 0。**上げない** |
| EXT-03 | IMPLEMENTED | IMPLEMENTED | Promotion へ配線（TD112 解消）。Episode 0 |
| EXT-09 | PARTIAL | **PARTIAL** | 危険検出は入ったが、未知の危険への判断能力は未測定 |
| SEC-06 | PARTIAL | **PARTIAL** | allowlist は埋まったが `security_status` の 20/22 が UNKNOWN |
| QA-05 | PARTIAL | **IMPLEMENTED** | mutation 全数自動化。ただし Promotion 系のみ（TD119） |

**Evidence が足りないものは上げていない。** EXT-10 と EXT-03 は実装が
進んだが Status を据え置いた。


---

# 001A — 独立レビュー修正（2026-09-04）

独立レビューで Major 2 件・Medium 1 件が残った。**指摘はすべて正しかった。**

## Major 1: fake digest で Registry を通せた

### 何が悪かったか

```python
if not manifest.promotion_decision_digest:
    raise ValueError(...)
```

**非空かしか見ていなかった。** したがって

```python
replace(manifest, status=PROMOTED, promotion_decision_digest="fake")
```

で Registry を通せた。**実際に再現した**（修正前に走らせて確認）。

> 「`promoted()` だけが digest を埋める」というコメントは、Python の
> dataclass / `replace` に対する Security Boundary にならない。

レビューのこの一文が核心である。私はコメントを保証と取り違えていた。

### どう直したか——digest を信用するのをやめた

Attestation は「通った」という**結論**ではなく、Gate が判定に使った
**入力一式**を持つ。Registry と Store は、その入力で
`evaluate_promotion` を**もう一度走らせて**から受け入れる。

```text
以前: 「通ったよ」という印を信じる
いま: 「通ったと言うなら、その入力でもう一度やってみせろ」
```

install / load 時に見るもの:

| # | 検査 | 何を止めるか |
|---|---|---|
| 1 | Attestation の存在 | Gate 未通過 |
| 2 | capability_id 一致 | 他 Capability の決定の流用 |
| 3 | digest == Attestation から再計算 | Attestation のすり替え |
| 4 | Manifest digest 一致 | 検証後の Manifest 書き換え（TOCTOU） |
| 5 | **再評価して allowed** | 「通ったよ」の自己申告 |
| 6 | Activation の identity | 載せる物 ≠ 検証した物 |

**Registry と Store は同じ 1 関数を呼ぶ**（`promotion_verification.py`）。
2 箇所に書くとずれる——`os_isolated` で実際にずれた。

### 正直な限界

**同一プロセス内の任意コードに対する暗号的境界ではない。**
`evaluate_promotion` 自体を差し替えられれば何でも通る。Python の
プロセス内でこれ以上の保証は作れない。

止まるのは「Gate を通さずに PROMOTED を名乗る」であり、偽造しようとすると
**本当に Gate を満たす入力**を作る羽目になる。それは偽造ではない。

## Major 2: Manifest digest が production 未配線

`verified_manifest_digest` / `promoted_manifest_digest` は
**両方空なら拒否されなかった**。しかも production はそれを渡していなかった。
つまり既存の `test_a_swapped_manifest_is_refused` は人工的な unit test であり、
production binding の証明になっていなかった——レビューの指摘どおりである。

直したこと:

- **両方空 → 拒否**（`artifact_digest_missing`）
- BUILD_TIME は build 時点の Permission Manifest digest を先に固定し、
  昇格時に計算し直して突き合わせる（**同じ値を 2 回計算して自分と比べる茶番にしない**）
- 宣言経路も渡す
- Attestation が `extension_manifest_digest`（status と promotion 系を除いた
  ExtensionManifest の正準 digest）へ束縛される。**昇格後に route / evidence /
  確認要否 / label を書き換えると install が落ちる**

## Medium: UNKNOWN 依存 Policy の矛盾

docstring は「既定は拒否側」、実装の既定は `ALLOW_IF_BUNDLED` だった。
**docstring 側を正とし、既定を `REJECT` へ変更した。**

`ALLOW_IF_BUNDLED` を使う経路は**呼び出し側が明示的に選ぶ**。
選んだ事実は Evidence の `unknown_security_policy` に残る。

本番 BUILD_TIME は `ALLOW_IF_BUNDLED` を明示的に選んでいる。理由は
「Forge が既に同梱していて、生成物のための新規取得が発生しないもの」に
限るからである。**それでも「脆弱性が無いと確認した」ではない。**
SEC-06 は `PARTIAL` のままにする。

## 追加破壊試験（22 件）

| 攻撃 | 結果 |
|---|---|
| `promotion_decision_digest="fake"` | 拒否 |
| ランダム 64hex digest | 拒否 |
| Attestation は本物・digest だけ差し替え | 拒否 |
| 他 Capability の決定を流用 | 拒否 |
| 拒否される入力の Attestation を持ち込む | 拒否（再評価） |
| 昇格後に確認要否を変更 | 拒否 |
| 昇格後に route を変更 | 拒否 |
| 昇格後に evidence を弱める | 拒否 |
| Attestation の権限を追加（権限昇格） | 拒否 |
| 人の承認を偽造 | 拒否 |
| 承認の**出所**だけ書き換え | 拒否 |
| 未 allowlist 依存へすり替え | 拒否 |
| 危険 Effect を追加 | 拒否 |
| Manifest 未束縛の Attestation | 拒否 |
| `bound_to_manifest("")` | 拒否 |
| **Store: 偽 digest + envelope SHA を再計算** | 拒否（load 時に再評価） |
| Store: Attestation を剥がす | 拒否 |
| Store: 保存後に権限を昇格 | 拒否 |
| Store: 保存後に Manifest を編集 | 拒否 |

**Store の SHA256 は改ざん検知の identity であって、Gate 通過の証明ではない。**
正しく計算し直した改ざんは SHA では捕まらない。捕まえるのは再評価である。

## Mutation: 26 → 36 件

新設 10 件。**うち 4 件は最初 FAIL した**——私が書いたばかりの試験が
置物だった。

```text
manifest_digest_presence_at_install  → 置物（試験を書き足して解消）
manifest_digest_presence_in_gate     → 置物（同上）
store_reverifies_on_load             → 置物（round-trip 改ざん試験へ差し替え）
registry_requires_decision_digest    → 陳腐化（実装の変更に追随させた）
```

**書いた直後の試験でも置物になる。** 破壊試験をしなければ「PASS している」と
報告していた。最終的に **36/36 検出**。

Gate 拒否理由（enum）だけでなく、**Registry / Store の検証不変条件 10 件**も
一覧化した。これが壊れると拒否理由を 1 つも変えずに偽造が通るためである。

## 検証

forge_ai **895 passed / 11 skipped**、backend **2073 passed / 16 skipped**、
mutation **36/36 検出**、Capability Matrix PASS、Universal Quality PASS、lint PASS。

## Windows 実機

**Windows Sandbox backend 自体は変更していない。** ただし Promotion の
**本番配線**を変えたので、Promotion 経路だけの再試験を用意した。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows_promotion_gate_revalidation.ps1
```

1 本で完結し、最後に `RESULT: ALL PASS` / `RESULT: FAIL (...)` が 1 行出る。
`FORGE_SANDBOX_ALLOW_POLICY_ONLY` を**明示的に削除**してから走るので、
policy-only で誤魔化した結果にはならない。
**TD110 physical probes の全再実行は不要。**
