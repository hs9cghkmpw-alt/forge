# Sandbox 実装と 121 能力の実態確定 — 2026-09-04

**Base HEAD:** `ba0233fcb765c7c989fa9cd803150d7087cc08c0`

**Branch:** `claude/forge-master-handoff-k46jns`

---

## 0. まず、簡単な言葉で

今回は**測り方を作る作業ではなく、実際に穴を塞ぐ作業**をした。

1. **AI が書いたコードを、隔離した檻の中で動かすようにした。**
   これまでは Forge を動かしているパソコンの権限そのままで動いていた。
   ネットにも出られたし、環境変数（API キーなど）も見えていた。
   いまは、ネットに出られない・秘密が見えない・時間とメモリに上限がある
   状態でしか動かない。**檻を作れない環境（Windows）では、動かさない。**

2. **危ない操作は人の承認が要るようにした。**
   ネット接続・ログイン情報・支払い・取り消せない操作を含む道具は、
   人が承認するまで動かないし、取り込まれもしない。
   利用者には「インターネットへ接続します」のような**普通の言葉**で見せる。

3. **勝手に外部のコードを取ってくるのを禁止した。**
   `pub get` や `pip install`、`curl` で何か落としてくる、を拒否する。

4. **121 個の能力のうち、見ていなかった 102 件を 59 件まで減らした。**

**まだ言えないこと**も先に書く。Windows では檻がまだ無い。だから
「Sandbox 完成」とは書かない。99% を証明した能力は**まだ 0 件**である。

---

## 1. 前回の判断の訂正（CEO 指示 §1 / §2）

前回、Frozen Final Holdout と Human 400 人を**開発の停止理由のように**扱った。
誤りである。CEO 指示により次のとおり分ける。

```text
Implementation blocker          ≠ Frozen Holdout / Human 400
Final 99% certification blocker = Frozen Holdout / Human 400
```

### 対応

| 項目 | 対応 |
|---|---|
| Holdout の暫定運用を確定 | `docs/evidence/holdout/HOLDOUT-SPECIFICATION.md`。**Repository に問題本体を置かない**。RC Freeze 後に独立生成 |
| 置くもの | specification / family allocation / scoring contract / runner / result schema / hash・provenance format |
| Runner | `scripts/holdout_runner.py`。`--created-by` が開発 Agent なら**拒否**。問題集合が Repository の中にあっても**拒否** |
| Human の段階分離 | `PRE_HUMAN_READY` を Status 語彙へ追加。`IMPLEMENTED → 自動/内部検証 → PRE_HUMAN_READY → Human Evidence → 99_PROVEN` |

`PRE_HUMAN_READY` は `human_evidence_required: true` の Capability だけが
名乗れる（人を待っていないなら、そのまま先へ進める）。検査器が強制する。

---

## 2. ADR-015 の再監査（CEO 指示 §3）

**Status を `ACCEPTED` → `PROVISIONAL` へ格下げした。**

### なぜ格下げしたか

初版は「現在の Typed IR では GEN-09/10/11 を表現できない」を根拠に
Generated Source を必要と結論した。しかし

> **「現在の語彙で表現できない」と「Typed IR を拡張しても表現できない」は
> 別の主張である。**

初版はその区別をせずに ACCEPTED を名乗っていた。過剰である。

### 14 軸比較の結果（要約）

| | A: Extended Typed IR | B: Generated Source | C: Hybrid |
|---|---|---|---|
| 強い軸 | Security / Determinism / Validation / Reuse / AI dependence / Offline / Evidence | Extension speed / Future scalability / Performance | 両方の中間 |
| 弱い軸 | Extension speed / Maintainability（Forge 本体が肥大） | Security / Determinism / Reuse / Offline | Maintainability |

**A が強い軸は Forge の中核価値とほぼ一致する。**

### GEN-09/10/11 は本当に Source 生成を要するのか

| ID | 再判断 |
|---|---|
| GEN-09 特殊 UI | **A で届く可能性が高い。** Encoding（値→視覚属性の写像）と View（レイアウト規則）は宣言で書ける領域 |
| GEN-10 ゲーム | **A で届く可能性が高い。むしろ A の方が安全。** Game Rule IR + 決定論的 engine（ECS / rule engine）は確立技術。Loop と Collision は Forge が書き、Rule だけ宣言させる。無限ループが構造的に書けなくなる |
| GEN-11 インタラクティブ UI | **A で届く可能性が高い。** Flutter 自身が既に宣言的 Animation の形（`AnimatedContainer`） |
| EXT-04 コード生成 | **B が要る**（定義そのもの） |
| EXT-06 Runtime 登録 | **A なら不要化しうる** |

初版の結論は誤りではないが、**根拠が弱かった。「いま無い」を「原理的に
できない」と読んでいた。**

### 暫定決定

> **C（Hybrid）。ただし「Typed IR を先に拡張する」を既定の向きとし、
> Source 生成は最後の手段とする。**

```text
1. 既存 Typed IR で作れるか  → 作る（Reuse-first）
2. Typed IR の拡張で作れるか  → **IR を拡張する**（Forge 本体の仕事）
3. どうしても表現できないか   → **理由を Evidence に残したうえで** Source 生成
```

3 へ落ちた理由を残さない Source 生成を禁止する——それが Drift の始まりである。

**既存の Generated Dart 経路は削除していない。** 動いているものを止めずに
Architecture を決めた（CEO 指示 §3）。

ACCEPTED へ戻す条件として Decision Experiment E1〜E4 を ADR §7 に定義した。

---

## 3. 実装した Gap（CEO 指示 §6 / §7 / §8）

### 3.1 Sandbox（EXT-08 / SEC-04）

`forge_ai/core/sandbox/runner.py`

| 閉じたもの | 手段 |
|---|---|
| Network | Network namespace（`unshare -n`）。**loopback すら無い** |
| Process | **PID namespace**（`--pid --fork`）。host の process を見ることも signal することも出来ない |
| 環境変数 / Secret | **env を空から作り直す。** 継承しない |
| CPU 時間 | `RLIMIT_CPU` + 壁時計 timeout（**別々に**効くことを試験で分離） |
| Memory | `RLIMIT_AS` |
| 出力ファイルサイズ | `RLIMIT_FSIZE` |
| Process 数 | `RLIMIT_NPROC`（**root では効かない。下記参照**） |
| 無限実行 | timeout → process group ごと kill |
| Workspace | cwd を明示 workspace に固定。存在しない workspace は拒否 |
| shell | 通さない（argv のみ受け取る） |

**AST の禁止語チェックを Sandbox と呼んでいない。** OS の機能で実際に閉じている。

### 3.2 Windows を「あとで」にしていない

**Windows / macOS backend は未実装である。** その環境では
`SandboxUnavailable` を送出して**実行を拒否する**（fail closed）。

「Sandbox が無い環境では素通しで実行する」は最悪の設計であり、
それをしないことが `test_it_refuses_to_run_without_a_backend` の目的である。

したがって EXT-08 / SEC-04 は **`PARTIAL`**（`IMPLEMENTED` ではない）。
Linux だけ通ったことを「Sandbox 完成」と読まない。

### 3.3 本番経路へ繋いだ

Sandbox を書いただけでは意味が無い（「作ったが本番から呼ばれない」）。
生成物を実際に走らせる唯一の場所 `build_time_workspace._execute` を
Sandbox 経由へ変えた。

`CommandEvidence` に `sandbox_backend` を足し、**どこで動かしたかを
Evidence が持つ**ようにした。空なら隔離されていない。

配線破壊: `_execute` を素の `subprocess.run` へ戻すと 2 件 FAIL。

### 3.4 Permission Manifest と Tier 強制（EXT-03 / EXT-09）

`forge_ai/core/sandbox/policy.py`

- Permission は**列挙型**。自由文字列を許さない（「これは permission ではない」
  という言い訳が効かないように）
- **Tier は権限から計算する。申告を信じない。** Network を持つ「Tier A」は拒否
- Tier C（Network / Credential / OS / 決済 / 不可逆 / process 起動）は
  **Human Gate 必須**。Promotion にはさらに承認の出所が要る
- 利用者へは「インターネットへ接続します」のような**普通の言葉**へ直す。
  拒否メッセージも同じ言葉で出す（内部語彙を丸投げしない）

### 3.5 依存の閉鎖（SEC-06）

- allowlist に無い依存を拒否。**「たぶん安全な有名 package」も拒否する**
  （安全かどうかを Forge が確かめていないため）
- `pub get` / `pip install` / `npm i` / `curl` / `wget` / `git clone` /
  `apt-get` / `cargo add` / `go get` を検出して拒否
- **argv の list 形も検出する。** 試験中に `['pip', 'install', ...]` を
  取りこぼしたため、引用符とカンマを潰してから走査するよう直した。
  **書き方を変えれば通る検出器は検出器ではない**

---

## 4. Before / After（CEO 指示 §10）

架空の「2億円版 Score」とは比較しない。**Target Contract との差**で書く。

### EXT-08 Sandbox実行（Target: 100%境界 / Network・File・Process・Secret escape 0件）

```text
Before:
  NOT_STARTED
  Sandbox escape protection = none
  生成物の test/build を**ホスト権限**で実行（network 可、env 継承）

After:
  PARTIAL
  Linux: network / PID / env / CPU / memory / file size の 6 gate 実装
  escape corpus 8/8 遮断（network, DNS, secret, host env, 無限ループ,
                          memory bomb, fork bomb 封じ込め, 巨大ファイル）
  本番経路（build_time_workspace._execute）へ配線済み・破壊試験済み
  Windows/macOS: **未実装 → 実行を拒否（fail closed）**

Remaining:
  Windows backend、Windows 実機 evidence、
  root 実行時の process 数上限（RLIMIT_NPROC は root で効かない）、
  AST/Import/Secret/Effect の静的検査（SEC-05）、
  Frozen Holdout、required episode count
```

### EXT-03 新Capability定義（Target: 完全な Typed Contract と Permission Manifest）

```text
Before: PARTIAL — Typed Contract のみ。Permission Manifest 無し
After:  IMPLEMENTED — Permission Manifest（列挙型・Tier 計算・Human Gate）
Remaining: Promotion 判定への配線、Corpus 測定
```

### EXT-09 自動安全性判断（Target: 100%重大検出 / P0・P1 false negative 0件）

```text
Before: NOT_STARTED — Sandbox が無いため判断自体が成立しない
After:  PARTIAL — 権限から Tier を計算し Tier C を Human Gate で止める
Remaining: P0/P1 の危険検出そのもの（AST/Effect 解析、SEC-05 依存）
```

### SEC-06 Dependency検査（Target: 100%重大検出 / Unknown・禁止・重大脆弱 0件）

```text
Before: （誤配置。External call default deny を入れていた）
After:  PARTIAL — allowlist 機構と取得行為の拒否
Remaining: **allowlist の中身が空**。License / Digest / 脆弱性情報が無い
```

### SEC-04 Sandbox（Target: 100%境界 / OS別 escape corpus 全遮断）

```text
Before: NOT_STARTED
After:  PARTIAL — Linux corpus のみ
Remaining: Windows / macOS corpus。**Target は「OS別」である**
```

---

## 5. 自分の誤配置を訂正した（重要）

**Capability 名を読まずに検索語を置いたため、4 件を別の能力の実装で
埋めていた。** 2026-09-04 に訂正した。

| ID | 正しい能力 | 誤って入れていたもの | 訂正後 |
|---|---|---|---|
| SEC-06 | Dependency検査 | External call default deny | 依存 allowlist へ差し替え → PARTIAL |
| SEC-07 | Secret管理 | 依存 allowlist | Secret 経路（Prompt/Log/Dataset/Screenshot）へ差し替え → PARTIAL |
| QA-05 | 配線破壊試験 | Evidence integrity（TD104） | Guard-break 運用へ差し替え → PARTIAL |
| UI-11 | 特殊UI（Canvas/Timeline/Grid/Scene） | Provider 非依存 UI（AIモード） | **NOT_ASSESSED へ戻した** |

「AIモード」の作業は 121 のどれにも対応しない（Constitution §4 / §9 の要件で
あって能力項目ではない）。`capabilities.json` の `unmapped_work` へ記録した。

**この訂正で `IMPLEMENTED` は 21 → 17 に減った。** 数字は悪くなったが、
それが正しい（CEO 指示 §11）。

---

## 6. 121 能力の状態（CEO 指示 §4）

| Status | Before（2026-09-03） | After（2026-09-04） |
|---|---:|---:|
| `NOT_ASSESSED` | 102 | **58** |
| `NOT_STARTED` | 2 | 20 |
| `DESIGNED` | 0 | 1 |
| `PARTIAL` | 5 | 25 |
| `IMPLEMENTED` | 12 | 17 |
| `VERIFIED` | 0 | 0 |
| `PRE_HUMAN_READY` | — | 0 |
| **`99_PROVEN`** | **0** | **0** |
| **`HARD_GATE_PROVEN`** | **0** | **0** |

**NOT_ASSESSED: 102 → 58（44 件を評価）。**

Mapping Index（`docs/evidence/capability_matrix/mapping_index.json`）を
`scripts/build_capability_mapping_index.py` で生成した。
**候補抽出までが仕事**であり、Status は意味を確認して決めた。

---

## 7. Gap Priority（CEO 指示 §5）

各 Capability へ `gap` を足した。

```json
"gap": {
  "target_level": "99_PROVEN / HARD_GATE_PROVEN",
  "current_level": "...", "gap_steps": 0-6,
  "blast_radius": 1-5, "implementation_cost": 0-5,
  "evidence_cost": 3-5, "risk": "high|medium|low",
  "priority_score": (gap_steps * blast_radius * hard_gate) / (impl_cost + evidence_cost)
}
```

**最少の 0 円作業で最大数の Gap を縮める向き**に、cost を分母へ置いた。

### 未解決 Top 10（priority_score 順）

| # | ID | 能力 | Status | score |
|---|---|---|---|---:|
| 1 | SEC-05 | Generated Code検査（AST/Import/Secret/Effect） | NOT_STARTED | 6.0 |
| 2 | EXT-08 | Sandbox実行（Windows backend） | PARTIAL | 6.67 |
| 3 | SEC-04 | Sandbox（OS別 corpus） | PARTIAL | 6.67 |
| 4 | EXT-09 | 自動安全性判断 | PARTIAL | 4.0 |
| 5 | SEC-06 | Dependency検査（allowlist の中身） | PARTIAL | 4.0 |
| 6 | QA-05 | 配線破壊試験の自動化 | PARTIAL | 4.0 |
| 7 | EXT-11 | 新能力の再利用（TD97: process ローカル） | PARTIAL | 3.0 |
| 8 | EXT-14 | 完全自律ループ（実 Local Model 0 回） | PARTIAL | 3.0 |
| 9 | PER-01 | Conversation速度（p95/p99 未測定） | PARTIAL | 3.0 |
| 10 | LRN-01 | Generation記録（Outcome 指標未収録） | PARTIAL | 3.0 |

---

## 8. 検証

| 検証 | 結果 |
|---|---|
| `pytest forge_ai/tests` | **783 passed / 10 skipped**（前回 747、+36） |
| `pytest backend/tests` | **2066 passed / 16 skipped** |
| `flutter analyze --fatal-infos --fatal-warnings` | No issues found |
| `flutter test` | （下記 CI 参照） |
| `check_universal_quality_policy.py` | PASS |
| `check_capability_matrix.py` | PASS |
| Real Provider calls | **0 件** |
| Real Local Model runs | **0 回** |
| Human Evidence | **0 人** |

### 8.1 配線破壊試験（CEO 指示 §9）

**1 つずつ意図的に壊し、落ちることを確認した。**

| 壊したもの | 結果 |
|---|---|
| Network namespace を外す | **2 件 FAIL** |
| env を継承させる（Secret を渡す） | **2 件 FAIL** |
| CPU 上限を外す | **1 件 FAIL** |
| Memory 上限を外す | **1 件 FAIL** |
| File size 上限を外す | **1 件 FAIL** |
| backend 無しでも実行する（fail open） | **1 件 FAIL** |
| 本番経路が Sandbox を通らない | **2 件 FAIL** |
| Tier を申告どおり信じる | **5 件 FAIL** |
| Tier C の Human Gate を外す | **2 件 FAIL** |
| 承認の出所要求を外す | **1 件 FAIL** |
| 依存 allowlist を外す | **1 件 FAIL** |
| 依存獲得の走査を外す | **1 件 FAIL** |
| 申告と計算の突き合わせを外す | **1 件 FAIL** |

**13/13 検出。** すべて復元して全 PASS を確認した。

### 8.2 試験の途中で見つけた自分の置物（正直に書く）

最初に書いた試験のうち **2 件が置物だった**。

| 置物 | なぜ通ってしまったか | 直し方 |
|---|---|---|
| CPU 上限 | 上限を外しても**壁時計 timeout が代わりに拾って**いた | 壁時計を 60 秒に伸ばし、CPU 2 秒で止まることを時間で判定 |
| Memory 上限 | 同上（「終わらなかった」で満足していた） | **`MemoryError` が出ること**を要求 |

配線破壊試験をしなければ、この 2 件は「守っているつもり」のまま残っていた。

### 8.3 実測で分かった弱点（正直に書く）

**`RLIMIT_NPROC` は実効 UID が root のとき強制されない。**
上限 16 を設定して fork 400 が通った（2026-09-04 実測）。

したがって process の防御は **PID namespace が本体**であり、数の上限は
補助にすぎない。`describe_environment()['nproc_limit_effective']` で
この事実を Evidence 側から見えるようにした。
**効かない制限を「効く」と書かない。**

---

## 9. 「測定方法を作った」か「差を縮めた」か（CEO 指示・最後）

**今回は差を縮めた。** 内訳を分ける。

| 種類 | 内容 |
|---|---|
| **実際に差を縮めた** | EXT-08（NOT_STARTED→PARTIAL、escape corpus 8/8）、SEC-04（同）、EXT-03（PARTIAL→IMPLEMENTED）、EXT-09（NOT_STARTED→PARTIAL）、SEC-06（機構実装）。**生成物がホスト権限で動く状態を終わらせた** |
| 測り方を作った | Gap Priority、Mapping Index、Holdout 運用、`PRE_HUMAN_READY` |
| **差を広げた（訂正）** | 誤配置 4 件の訂正で `IMPLEMENTED` が 21→17 に減った。実態に合わせた |

**能力差 0・121項目 99%・Z12 完了は宣言しない。** `99_PROVEN` は 0 件である。

---

## 9.1 別 Agent の Sandbox 実装と重ねた

作業中に別 Agent が同じ branch へ Sandbox 系 22 commit を push していた
（`d5ae993`）。**どちらも消さずに重ねた。**

| 層 | 出所 | 内容 |
|---|---|---|
| Policy 層（`build_time_sandbox.py`） | 別 Agent | AST/import preflight、実行ファイル allowlist、実行ファイルの一度限りの解決と固定、env scrub、Host Projection binding、sandbox attestation を Promotion blocker に |
| OS 層（`core/sandbox/`） | 今回 | network / PID namespace、rlimit、timeout、workspace、shell 不使用 |

**Policy 層だけでは読み落とした 1 つで破れ、OS 層だけではどの実行ファイルが
選ばれたか分からない。** 向こうの docstring 自身が「A future OS backend can
sit underneath the same contract」「must not be described as the final EXT-08
proof by itself」と書いており、今回の OS 層はその下に入る形になった。

衝突は `_execute` と対応テストの 2 箇所。向こうの `resolve_executable` /
`build_environment` で argv と env を固定し、**それを** `run_in_sandbox` へ
渡す形へ解決した（`run_in_sandbox` に `env_override` を追加。渡されても
`os.environ` は継承しない）。テストは両者を残した。

- merge 後: forge_ai **803 passed** / backend **2072 passed**
- 配線破壊: `_execute` を素の `subprocess.run` へ戻すと 2 件 FAIL（再確認）
- SEC-05 が NOT_STARTED → **PARTIAL**（向こうの AST/import preflight による）

---

## 9.2 CI を落とした（正直に書く）

merge 後の CI run `33812200098` が **failure** だった。10 件 FAIL。

### 原因

**GitHub Actions の runner は `unshare` が在っても namespace を作れない**
（2026-09-04 実測）。したがって `available_backend()` が `None` を返し、
fail closed の Sandbox が生成物の実行を拒否し、**build が走ることを前提と
した既存試験 10 件が落ちた**。

自分のホスト（root、namespace 可）でしか確かめていなかった。
**「自分の環境で通った」を「通る」と読んだ**のが原因である。

### 直し方——保証を弱めずに直す

「CI だから素通しにする」はしない。代わりに **Policy 層だけの実行**という
段を明示的に作った。

| backend | 意味 |
|---|---|
| `linux-namespace+pid` | OS 層あり（network / PID namespace + rlimit） |
| `policy-only` | **OS 層なし。** Policy 層（AST 検査・実行ファイル固定・env scrub）のみ |
| `""` | 実行していない、または隔離を通っていない |

守った条件は 3 つ。

1. **既定は拒否のまま。** `FORGE_SANDBOX_ALLOW_POLICY_ONLY=1` の明示が要る
   （`external_call_policy` と同じ形。`.env` に置いたら勝手に開く、を作らない）
2. **名前に残す。** `policy-only` を `linux-namespace+pid` と混ぜない
3. **空文字にしない。** 空は「隔離せず走った」の意味であり別物

CI はこの変数を立てて走る（理由を `ci.yml` に書いた）。
**利用者の端末では変数が無いので拒否される。** Windows で Self-Extension が
動かないのは TD110 のとおりであり、それを隠す道ではない。

### 2 度目も落とした（同じ形）

`9cdb442` の CI run `33812952355` は backend / forge_ai が両方 success に
なったが、**frontend job の「生成 Dart の実ビルド経路」step が同じ理由で
落ちた**。opt-in を **step ごとに**書いていたため、別 job の step に
付け忘れた。

`did not produce a verified artifact` ——Sandbox が実行を拒否 → build 失敗
→ verified artifact 無し、という同じ連鎖である。

**「step を足すたびに思い出す」設計は忘れられる。** 2 回連続で忘れた。
したがって opt-in を **workflow 全体の `env:`** へ 1 箇所だけ置き直した。

### 3 度目——今度は別の原因だった

opt-in を workflow 全体へ置いた `211ae70` でも、frontend job の同じ step が
落ちた。**ここで「また opt-in の付け忘れだろう」と決めつけなかったのが
分かれ目**で、log を取り直したところ実行時間が **0.17s → 5.76s** に伸びて
いた。Sandbox は拒否しておらず、**中で Dart が起動できていなかった**。

原因は**私の既定値**である。`SandboxPolicy.memory_bytes = 512MB` は
`RLIMIT_AS`（**仮想**アドレス空間）へ入る。Python の小さな script なら
足りるが、**Dart VM は起動時に巨大な仮想領域を予約する**ため立ち上がれない。

手元では Python の subprocess でしか試していなかったので気付けなかった。

**推測で直さず、実測で確かめた**（CLAUDE.md「直す前に再現する」）。

```text
2GB の仮想領域を予約するだけのプログラムを Sandbox で実行

  default (512MB RLIMIT_AS)  → ok=False  OSError: Cannot allocate memory
  for_toolchain (8GB)        → ok=True   RESERVED 2GB OK
```

直し方は `SandboxPolicy.for_toolchain()` を足し、`build_time_workspace` が
それを使う。**緩めるが外さない**——`test_the_toolchain_policy_is_still_bounded`
が「どの上限も有限であること」「32GB を超えないこと」「network は開かない
こと」を固定する。上限を外して通す道は塞いだ。

### 再発防止

`unshare` を失敗する stub で置き換えて **CI 環境を手元で再現**し、
opt-in あり（`794 passed / 24 skipped`）と opt-in なし（`9 failed` = 拒否が
効いている）の両方を確認した。以後、Sandbox に触るときはこの再現を通す。

---

## 10. 新規 TECH_DEBT

| ID | 内容 |
|---|---|
| TD110 | Windows / macOS の Sandbox backend が無い。fail closed で拒否するため安全だが、**その環境では Self-Extension が動かない** |
| TD111 | `RLIMIT_NPROC` が root 実行で効かない。PID namespace で隔離はするが process 数は止まらない |
| TD112 | Permission Manifest を Promotion 判定へ配線していない。Manifest は作れるが、無いまま Promotion できる |
| TD113 | 依存 allowlist の中身が空。License / Digest / 脆弱性情報を持っていない |
| TD114 | 自分の誤配置（SEC-06/07・QA-05・UI-11）。Capability 名を読まずに検索語を置いた。**Mapping Index を結論として使わない**運用で再発を防ぐ |
| TD115 | Sandbox を自分のホスト（root・namespace 可）でしか確かめず CI を落とした。`policy-only` 段を足して直したが、**環境差を先に確かめる**手順が要る |

---

## 11. 最終報告（CEO 指示 §12）

### 11.1 事実

| 項目 | 値 |
|---|---|
| 開始 HEAD | `ba0233fcb765c7c989fa9cd803150d7087cc08c0` |
| 最終 Commit | `59e38d6a515cabf56ead22d7e44f6eb15d70fd07` |
| Commit 数 | 28（別 Agent の 22 commit との merge を含む） |
| 変更規模 | 49 files / +11,423 / −619 |
| CI | **success**（run `33813646772` / 4 job すべて success） |
| CI で実際に走った重い step | 「生成 Dart の実ビルド経路」→ `test exit=0` / `build exit=0` / `runtime_probe exit=0` / `PROMOTED` |

CI は 3 回落ちてから緑になった（§9.2）。**1 回目で緑にはならなかった**。

### 11.2 121 能力の Status（Before → After）

| Status | Before | After | 差 |
|---|---:|---:|---:|
| `NOT_ASSESSED` | 102 | **58** | **−44** |
| `NOT_STARTED` | 2 | 19 | +17 |
| `DESIGNED` | 0 | 1 | +1 |
| `PARTIAL` | 5 | 26 | +21 |
| `IMPLEMENTED` | 12 | 17 | +5 |
| `VERIFIED` | 0 | 0 | 0 |
| `PRE_HUMAN_READY` | 0 | 0 | 0 |
| `99_PROVEN` | **0** | **0** | **0** |
| `HARD_GATE_PROVEN` | **0** | **0** | **0** |

`NOT_ASSESSED` −44 の内訳で**一番多いのは `NOT_STARTED` と `PARTIAL`**、つまり
**「見たら無かった」「見たら一部だけだった」**である。上げた数ではなく、
**見た数**が増えたと読むのが正しい。

### 11.3 検査した / 上げた / 下げた Capability ID

**検査した: 63 件**（121 − 58）。うち状態が動いたのは 51 件。

**上げた: 48 件**

```text
AI-03 AI-08 / GEN-07 GEN-12 GEN-13 GEN-14
EXT-03 EXT-07 EXT-08 EXT-09
LOC-05 LOC-09 / LRN-01 LRN-05 LRN-06 LRN-08 LRN-09 LRN-12
UI-05 UI-07 UI-12 UI-13 UI-14
QA-01 QA-03 QA-04 QA-08 QA-09 QA-11
SEC-01 SEC-03 SEC-04 SEC-05 SEC-07 SEC-10
PRD-01 PRD-02 PRD-06 PRD-07 PRD-08 PRD-09 PRD-12 PRD-15
PER-01 PER-02 PER-06 PER-07 PER-08
```

このうち **17 件は `NOT_ASSESSED → NOT_STARTED`**、つまり
**「見た結果、無いと確認した」**であって能力が増えたのではない。

**下げた: 3 件**（指示 §11「Evidence 不足を見つけたら下げる」）

| ID | 能力 | Before → After | 理由 |
|---|---|---|---|
| UI-11 | 特殊 UI | `IMPLEMENTED` → `NOT_ASSESSED` | 私が別能力の実装で埋めていた（TD114） |
| QA-05 | 配線破壊試験 | `IMPLEMENTED` → `PARTIAL` | 同上 |
| SEC-06 | Dependency 検査 | `IMPLEMENTED` → `PARTIAL` | 同上 |

**Matrix の数字は下がる方向にも動かした。** `IMPLEMENTED` は自分の誤配置訂正で
21 → 17 へ落ちている。

### 11.4 2億円 Target との差を実際に縮めたもの

**架空の「2億円版 Score」とは比較しない**（指示 §10）。Target Contract に対する
差だけを書く。

| Capability | Target Contract | Before | After | 実際に縮んだか |
|---|---|---|---|---|
| SEC-04 Sandbox | 生成物が OS 資源を越えない | 隔離**無し**（素の `subprocess.run`） | network/PID namespace + rlimit + 壁時計、本番経路が通る | **縮んだ** |
| EXT-08 Sandbox 実行 | 自己拡張が隔離下で動く | `NOT_STARTED` | `PARTIAL`（Linux のみ） | **縮んだ**（Windows は未達） |
| SEC-03 Permission | 危険能力に Human Gate | 判定機構**無し** | Tier を permission から**計算**、Tier C は承認無しで実行/Promotion 不可 | **縮んだ** |
| SEC-06 Dependency 検査 | 未検証の依存を入れない | allowlist 無し | allowlist + 獲得行為（`pip install` 等 15 種）を検出し拒否 | **縮んだ（部分）**——allowlist の中身は空（TD113） |
| SEC-05 生成 Code 検査 | AST/import/secret/effect | 無し | 別 Agent の preflight で `PARTIAL` | 縮んだ（他 Agent 分） |
| QA-05 配線破壊試験 | Gate が実際に効く | 一部 | Sandbox 13 種の配線破壊で**全件検出**、うち**自分の置物 2 件を発見して修正** | 縮んだ |

**縮んでいないもの:** GEN 系（生成能力そのもの）、UI 系、LRN 系、PRD 系。
今回は**Foundation を 1 本通した**のであって、生成能力は上がっていない。

### 11.5 ADR-015 の最終 Status

**`PROVISIONAL`**（`ACCEPTED` から格下げ）。

- 格下げ理由: 「現在の Typed IR で表現できない」を「拡張しても表現できない」と
  読んでいた。根拠が主張に足りていない
- 14 軸比較の結論: A（Extended Typed IR）が **Security / Determinism /
  Validation / Reuse / AI dependence / Offline** で強い。これは Forge の
  中核価値とほぼ一致する
- GEN-09 / GEN-10 / GEN-11 は **A で届く見込みが高い**（Game Rule IR /
  Interaction IR / Encoding IR）。B が定義上必要なのは **EXT-04 のみ**
- 既定の向き: **IR 拡張が先、Source 生成は最後の手段、落ちた理由を必ず記録**
- **既存 Generated Dart 経路は削除していない**（指示 §3）
- `ACCEPTED` へ戻す条件: Decision Experiment E1〜E4 の実測

### 11.6 Sandbox / Tier / Permission / 依存 の状態

| 項目 | 状態 |
|---|---|
| Sandbox（Linux） | **動作。** network namespace / PID namespace / RLIMIT_CPU・AS・NPROC・FSIZE / 壁時計 timeout / 明示 workspace / env をゼロから再構築 / shell 不使用 |
| Sandbox（Windows・macOS） | **未実装。拒否する**（fail closed）。**Linux だけ通ったことを「完成」と書かない**（TD110） |
| 本番経路への配線 | `build_time_workspace._execute` の 1 箇所。ここを素の `subprocess.run` へ戻すと試験 2 件が FAIL |
| `policy-only` 段 | CI 等 namespace を作れない環境向け。**既定は拒否**、明示 opt-in が要る、Evidence に名前が残る |
| Tier 強制 | **動作。** Tier は宣言を信じず permission から**計算**。Tier C は `human_approval` 無しで実行不可、`approval_reference` 無しで Promotion 不可 |
| Permission Manifest | **作れるが、Promotion 判定へ未配線**（TD112）。**Manifest 無しでも Promotion できてしまう** |
| 依存 allowlist | 機構は動作。**中身が空**（License / Digest / 脆弱性情報を持っていない）(TD113) |
| 利用者向け言語 | `_USER_FACING` で「インターネットへ接続します」等へ変換。専門用語を利用者へ出さない試験あり |

### 11.7 試験

| 対象 | 結果 |
|---|---|
| `forge_ai` | **811 passed / 10 skipped / 0 failed** |
| `backend` | **2072 passed / 16 skipped / 0 failed** |
| Capability Matrix 検査 | **PASS** |
| Universal Quality 検査 | **PASS** |
| CI（4 job） | **すべて success** |

skip 10 件は OS 層を要する escape corpus（policy-only 環境で正しく skip される分）
と Live Test（既定 SKIP）である。

### 11.8 配線破壊試験（指示 §9）

Gate を **1 つずつ外して、対応する試験が FAIL することを確認した。**

| 外したもの | 結果 |
|---|---|
| network namespace | 検出 |
| env の再構築 | 検出 |
| CPU 上限 | **最初は検出しなかった**（壁時計が先に効く置物だった）→ 試験を書き直して検出 |
| memory 上限 | **最初は検出しなかった**（同上）→ `blocked: MemoryError` を要求して検出 |
| file size 上限 | 検出 |
| fail closed（拒否せず素通し） | 検出 |
| PID namespace | 検出 |
| Tier 計算 | 検出 |
| Tier C の Human Gate | 検出 |
| Permission 検査 | 検出 |
| 依存 allowlist | 検出 |
| 獲得行為の禁止 | **最初は `['pip','install',...]` を見逃した** → **試験ではなく検出器を直した** |
| 本番経路の Sandbox 配線 | 検出（2 件 FAIL） |

**13/13 検出。ただし 3 件は最初 FAIL しなかった。** 置物を 2 つ自分で作って
いたことになる。破壊試験をしなければ「PASS している」と報告していた。

### 11.9 まだ言えないこと（Evidence が無いもの）

| 項目 | 実数 |
|---|---|
| Real Local Model runs | **0** |
| Real Provider 呼び出し | **0**（本 Task 中に実 API は一切呼んでいない） |
| 実機（Windows / Android / iOS）Evidence | **0** |
| Human Evidence | **0 人**（H0 の 3〜5 人も未実施） |
| Frozen Final Holdout | **未生成**（RC Freeze 後に独立生成する。仕様・割当・runner・result schema のみ Repository にある） |
| `99_PROVEN` | **0 件** |
| `HARD_GATE_PROVEN` | **0 件** |
| 0 円違反 | **0 件**（課金 API・有料 Service を使っていない） |

### 11.10 未解決 Gap Top 10

Priority Score 順（`gap` block より）。

| # | ID | 能力 | 現在 | Score | 残っているもの |
|---|---|---|---|---:|---|
| 1 | SEC-04 | Sandbox | `PARTIAL` | 6.67 | **Windows / macOS backend**。主配布対象が未対応 |
| 2 | EXT-08 | Sandbox 実行 | `PARTIAL` | 6.67 | 同上。Linux 以外で自己拡張が動かない |
| 3 | SEC-05 | 生成 Code 検査 | `PARTIAL` | 6.00 | secret / effect の検査、Promotion への配線 |
| 4 | SEC-06 | Dependency 検査 | `PARTIAL` | 5.33 | **allowlist の中身が空**。License / Digest / 脆弱性 |
| 5 | QA-05 | 配線破壊試験 | `PARTIAL` | 5.33 | Sandbox 以外の Gate へ横展開 |
| 6 | GEN-04 | Validator | `IMPLEMENTED` | 4.80 | Episode が無い（`VERIFIED` へ上がれない） |
| 7 | GEN-03 | Schema 正当性 | `IMPLEMENTED` | 4.80 | 同上 |
| 8 | EXT-10 | 自動 Promotion | `IMPLEMENTED` | 4.80 | **Permission Manifest が未配線**（TD112） |
| 9 | SEC-07 | Secret 管理 | `PARTIAL` | 4.00 | 実運用での検証 |
| 10 | EXT-09 | 自動安全性判断 | `PARTIAL` | 4.00 | Tier 判定は出来るが、判断根拠の Evidence が薄い |

**残り 58 件は依然 `NOT_ASSESSED`**——見ていない。これも未解決 Gap である。

---

## 11.11 7 問の自己監査（`PRODUCT-DIRECTION.md` §8）

| # | 問い | 答え |
|---|---|---|
| 1 | 生成アプリの**品質**を上げるか | **直接は上げない。** 上げたのは安全性である。ただし「生成物がホスト権限で走る」状態は品質以前の欠陥であり、そこを塞いだ |
| 2 | Local AI が将来**学習・利用**できる構造か | **一部。** `CommandEvidence.sandbox_backend` により「どの隔離で走ったか」が Evidence に残るので、学習時に policy-only と OS 層を混ぜずに済む。一方 Permission Manifest は Promotion 判定へ未配線のため、学習可能な Evidence として溜まっていない（TD112） |
| 3 | 片方を改善して**もう片方を後退**させていないか | **後退させた箇所が 1 つある。** Sandbox を fail closed にしたことで、**Windows では Self-Extension が動かなくなった**。これは隠さない（TD110）。以前は「動くが無防備」、いまは「安全だが動かない」。**無防備なまま動かすよりは正しい**と判断したが、Windows は主配布対象なので未達である |
| 4 | **Template 依存**を増やしていないか | 増やしていない。Widget / Template を 1 つも足していない。ADR-015 の再監査はむしろ逆向き（有限部品ではなく IR 拡張へ）である |
| 5 | **Production Path** へ本当に接続されているか | **接続されている。** 配線先は `build_time_workspace._execute` の 1 箇所で、ここは生成コードが実行される**唯一の**場所である。素の `subprocess.run` へ戻すと試験 2 件が FAIL する。CI でも実際に通っており（`test/build/runtime_probe exit=0` → `PROMOTED`）、**「作ったが本番から呼ばれない」にはなっていない** |
| 6 | Local AI 改善へ使える **Evidence** が残るか | **部分的に残る。** `sandbox_backend` は残る。しかし README §4 の Outcome 指標（`primary_success`、`repair_attempts`、`latency_p95`、`peak_rss_mb` 等）は依然**未収録**であり、学習に足りる Episode になっていない |
| 7 | 実装都合で**最終目標を縮小**していないか | **していない。** むしろ ADR-015 で「現在できない」を「原理的にできない」と読んでいた自分の結論を取り消し、目標側を戻した。Status も緩めず、誤配置 3 件を**下げた** |

**問題として報告するもの:** #3（Windows で動かなくなった）と #6（学習に足る
Evidence が溜まっていない）。どちらも縮小して済ませず、TD110 / README §4 として
残した。#3 の代替案は「Windows backend（AppContainer / Job Object）を実装する」
または「Windows では Cloud 実行へ委譲する」の 2 つで、**Trade-off は前者が
実装工数、後者が 0 円方針とオフライン性の後退**である。CEO 判断は不要——
どちらも実装で解けるため、次 Task の候補として Gap Top 1 に置いた。

---

## 12. 「測定方法を作った」のか「差を縮めた」のか

CEO 指示の最後の問いに、分けて答える。

### 12.1 測定方法を作っただけのもの

- 121 能力の `gap` block（Target / Current / Gap steps / Blast Radius /
  Implementation Cost / Evidence Cost / Risk / Priority Score）
- Mapping Index（`mapping_index.json`）——**候補抽出まで**の道具
- `PRE_HUMAN_READY` の新設と、`check_capability_matrix.py` の検査規則
- Holdout の仕様・Family 割当・result schema・runner
- Human Panel の段階計画（H0〜H3）

**これらは 2億円 Target との差を 1mm も縮めていない。** 差を**測れるように
しただけ**である。

### 12.2 実際に差を縮めたもの

- **Sandbox（OS 層）**。Before は隔離**ゼロ**——生成された Dart が
  `subprocess.run` で素通しに実行されていた。After は network / PID
  namespace と rlimit の下でしか動かない。**escape corpus 8/8 を実際に阻止**
- **Tier / Permission の強制**。Before は判定機構が**存在しなかった**。
  After は Tier C が承認無しで実行も Promotion も出来ない
- **依存獲得の禁止**。Before は生成物が `pip install` を書けた。After は拒否される
- **置物試験 2 件の除去**。「PASS していたが何も守っていなかった」試験を
  破壊試験で見つけて直した

**これは実装の差であって、生成能力の差ではない。**

### 12.3 したがって、いま言えること

> **Foundation（Security 層）の差は縮んだ。生成能力（GEN / UI / LRN）の差は
> 縮んでいない。**

そして次は言わない。

- **「能力差 0」とは言わない**——`99_PROVEN` が 0 件である
- **「121 項目 99%」とは言わない**——測定した Episode が無い
- **「Z12 完了」とは言わない**——Holdout も Human Evidence も無い
- **「Sandbox 完成」とも言わない**——Windows で動かない

CI が緑になったのは「壊れていない」ことの証明であって、
**「2億円 Target に届いた」ことの証明ではない。**
