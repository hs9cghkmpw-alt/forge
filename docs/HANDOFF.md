# Forge Handoff — current Source of Truth

---

## CEOへの依頼（最優先・上から順に）

0. **【訂正済み】Frozen Final Holdout と Human 400 は、開発の停止理由ではありません。**
   前回そのように書いたのは誤りでした（CEO 指示 2026-09-04）。
   `Implementation blocker ≠ Frozen Holdout` として分けました。
   Holdout は **RC Freeze 後に独立生成**し、Repository には仕様・割り当て・
   採点規則・runner・結果 schema だけを置きます
   （`docs/evidence/holdout/HOLDOUT-SPECIFICATION.md`）。
   **いま CEO の判断待ちで止まっているものはありません。**
   Human 評価が要る能力は `PRE_HUMAN_READY` で置き、実装は進めます。

0.5 **（参考）旧 0 番の内容 — Holdout の置き方**
   この Repository は開発 Agent が全部読めるので、最終 99% 証明用の
   Benchmark を平文で置いた時点で Holdout になりません。したがって
   **現在どの能力も `99_PROVEN` へ到達できません**。0 円で採れる案は 3 つ
   （別 Repository / CEO 手元 / Seed 保持）。詳細は
   `docs/evidence/capability_matrix/README.md` §3.2。どれを採るか決めて
   ください。

0.5 **Human Panel の募集経路を決めてください。** 0 円で独立初見 400 人を
   確保する経路が現在ありません。まず 3〜5 人の H0 から始めます。Claude 側
   では募集自体が出来ないため CEO の行動が要ります。詳細は
   `docs/reports/FORGE-HUMAN-PANEL-ACQUISITION-PLAN-20260903.md`。
   **現在の Human Evidence 人数は 0 人です。**

0.9 **Gemini 無料枠が 2 回分消費された可能性が高い（2026-09-02、事故報告）。**
   ブラウザ実描画の証拠を撮るために Claude 側の作業ホストで backend を
   起動したところ、そのコンテナの `backend/.env` に **実 API キーが入って
   いた**。`/api/v1/ai/converse` を 2 回送信した後に気付き、直ちに停止した。
   応答の `provider` が `"gemini"`（＝実際に応答を返した Provider を記録する
   `last_provider_used` 由来。呼ばれていなければ `"unknown"`）だったため、
   実 API が呼ばれたと判断する。キーの値は表示・記録・commit していない。
   `backend/.env` は gitignore 対象で git 追跡外である。
   以後このホストで backend を起動しない。詳細は
   `docs/reports/FORGE-PROVIDER-INDEPENDENT-UI-20260902-report.md` §0.1。
   **2026-09-03 に Architecture で塞ぎました**（`external_call_policy.py`、
   Default Deny）。API キーがあるだけでは、もう外部 Provider を呼びません。

1. **OpenAI API キーの失効手続き。** 以前のセッションでチャットへ貼られた
   `sk-proj-...` は Repository に保存していないが、**貼られた時点で漏れている**。
   OpenAI 管理画面から revoke（失効）してください。未完了です。
2. **ぱすとらる PC (Windows) の Puro（Flutter のバージョン管理ツール）問題。**
   `flutter run -d chrome` が SDK path 解決で止まる件は、**この Linux 実行
   ホストでは再現しません**（こちらは `/opt/flutter` で正常動作）。
   実機側で下記を実行し、出力を貼ってください（秘密情報は含みません）。

   ```powershell
   where.exe flutter
   puro ls
   puro env use stable
   flutter --version
   flutter doctor -v
   ```

3. ~~Universal QualityのConstitution追記承認~~ — **完了。** CEOが提案の
   正確な文面を確認し、2026-09-02に「いいよ、すべて承認」と明示承認した。
   Constitution §13へ追記済み。

---

## Sandbox 実装と 121 能力の実態確定（2026-09-04）

Base HEAD `ba0233f` から実装した。**今回は測り方ではなく、実際に穴を塞いだ。**

### 最終状態（この Task は完了。CI 緑）

| 項目 | 値 |
|---|---|
| 最終 Commit | `59e38d6` |
| CI | **success**（run `33813646772` / 4 job すべて success） |
| CI で実際に走った重い step | 「生成 Dart の実ビルド経路」→ `test exit=0` / `build exit=0` / `runtime_probe exit=0` / `PROMOTED` |
| forge_ai | 811 passed / 10 skipped |
| backend | 2072 passed / 16 skipped |
| Capability Matrix / Universal Quality | PASS |
| 配線破壊試験 | 13/13 検出（**うち 3 件は最初 FAIL しなかった**＝置物を自分で作っていた） |

**CI は 3 回落ちてから緑になった。** 3 回目は原因が別で、
「また同じだろう」と決めつけず log を取り直したのが分かれ目だった（report §9.2）。

### まだ言えないこと（数字で）

| 項目 | 実数 |
|---|---|
| `99_PROVEN` / `HARD_GATE_PROVEN` | **0 件 / 0 件** |
| Real Local Model runs | **0** |
| Real Provider 呼び出し | **0**（本 Task 中に実 API は一切呼んでいない） |
| 実機 Evidence（Windows / Android / iOS） | **0** |
| Human Evidence | **0 人** |
| Frozen Final Holdout | 未生成（RC Freeze 後に独立生成） |
| 0 円違反 | **0 件** |

> **「能力差 0」「121 項目 99%」「Z12 完了」「Sandbox 完成」は、いずれも
> 言えません。** 縮んだのは **Foundation（Security 層）の差**であって、
> **生成能力（GEN / UI / LRN）の差は縮んでいません。**
> CI が緑なのは「壊れていない」証明であって、Target 到達の証明ではありません。

全文は `docs/reports/FORGE-SANDBOX-AND-CAPABILITY-ASSESSMENT-20260904-report.md`
§11〜§12。

### 簡単な言葉で

1. **AI が書いたコードを、隔離した檻の中で動かすようにしました。**
   これまでは Forge を動かしているパソコンの権限そのままで動いていて、
   ネットにも出られたし、環境変数（API キーなど）も見えていました。
   いまは、ネットに出られない・秘密が見えない・時間とメモリに上限がある
   状態でしか動きません。**檻を作れない環境（Windows）では動かしません。**
2. **危ない操作（ネット接続・ログイン情報・支払い・取り消せない操作）は
   人の承認が要る**ようにしました。利用者には「インターネットへ接続します」
   のような普通の言葉で見せます。
3. **勝手に外部のコードを取ってくるのを禁止**しました。
4. 見ていなかった能力を **102 件 → 58 件**へ減らしました。

### Before / After（Target Contract との差）

| ID | Before | After | 残り |
|---|---|---|---|
| EXT-08 Sandbox実行 | NOT_STARTED（保護 none） | **PARTIAL**（Linux で escape corpus 8/8 遮断、本番経路へ配線） | Windows backend |
| SEC-04 Sandbox | NOT_STARTED | **PARTIAL**（Linux corpus のみ） | OS 別 corpus |
| EXT-03 新Capability定義 | PARTIAL（Contract のみ） | **IMPLEMENTED**（Permission Manifest） | Promotion への配線 |
| EXT-09 自動安全性判断 | NOT_STARTED | **PARTIAL**（Tier 計算 + Human Gate） | P0/P1 検出（SEC-05 依存） |
| SEC-06 Dependency検査 | 誤配置 | **PARTIAL**（allowlist 機構） | allowlist の中身 |

### ADR-015 を再監査し、`ACCEPTED` → **`PROVISIONAL`** へ格下げ

初版は「現在の Typed IR では GEN-09/10/11 を表現できない」を根拠にしていた
が、**「いま無い」と「原理的にできない」は別**である。14 軸で A/B/C を比較し、
**GEN-09/10/11 は Typed IR の拡張（Game Rule IR / Interaction IR /
Encoding IR）で届く見込みが高い**と判断し直した。

暫定決定は **C（Hybrid）だが「Typed IR を先に拡張する」を既定の向き**とし、
Source 生成は最後の手段。落ちた理由を残さない Source 生成を禁止した。
**既存の Generated Dart 経路は削除していない。**

### 自分の誤配置を 4 件訂正した

Capability 名を読まずに検索語を置いたため、SEC-06 / SEC-07 / QA-05 / UI-11 を
**別の能力の実装で埋めていました**。訂正の結果 `IMPLEMENTED` は 21 → 17 に
**減りました**。数字は悪くなりましたが、それが実態です。

### 121 状態

| Status | 2026-09-03 | 2026-09-04 |
|---|---:|---:|
| NOT_ASSESSED | 102 | **58** |
| NOT_STARTED | 2 | 20 |
| DESIGNED | 0 | 1 |
| PARTIAL | 5 | 25 |
| IMPLEMENTED | 12 | 17 |
| **99_PROVEN** | **0** | **0** |
| **HARD_GATE_PROVEN** | **0** | **0** |

### 検証

- `pytest forge_ai/tests`: **783 passed**（前回 747）
- `pytest backend/tests`: **2066 passed**
- `flutter analyze`: No issues / `flutter test`: **589 passed**
- **配線破壊試験 13 種、13/13 検出**
- 試験自体の置物を 2 件発見して直した（CPU 上限 / Memory 上限が
  timeout に拾われていた）
- 実測で判明: **`RLIMIT_NPROC` は root では効かない**。PID namespace が本体
- Real Provider calls **0** / Real Local Model runs **0** / Human Evidence **0 人**

### 別 Agent の Sandbox 実装と重ねた（重要）

作業中に、別の Agent が同じ branch へ Sandbox 系の実装を push していました
（`d5ae993`、22 commit）。**どちらも消さずに重ねました。** 競合ではなく補完です。

| 層 | 誰 | 何を閉じるか |
|---|---|---|
| **Policy 層**（`build_time_sandbox.py`） | 別 Agent | 生成 Source の AST/import preflight、実行ファイル allowlist、実行ファイルをホスト上で一度だけ解決して固定（PATH 差し替え防止）、環境変数 scrub、Host Projection binding、sandbox attestation を Promotion blocker に |
| **OS 層**（`core/sandbox/`） | 今回 | network namespace、PID namespace、RLIMIT_CPU/AS/FSIZE、壁時計 timeout、明示 workspace、shell 不使用 |

Policy 層だけでは「読み落とした 1 つ」で破れます。OS 層だけではどの実行
ファイルが選ばれたか分かりません。**両方要ります。**

向こうの docstring 自身が「A future OS backend can sit underneath the same
contract」「must not be described as the final EXT-08 proof by itself」と
書いており、今回の OS 層はちょうどその下に入りました。

衝突は `_execute` と対応テストの 2 箇所。向こうの `resolve_executable` /
`build_environment` で argv と env を固定し、**それを** `run_in_sandbox` へ
渡す形へ直しました（`env_override` を追加。渡されても `os.environ` は
継承しません）。テストは両者を残しました。

この結果 SEC-05（Generated Code検査）が NOT_STARTED → PARTIAL になりました。

### CI を一度落としました（正直に書きます）

merge 後の CI run `33812200098` が failure（10 件 FAIL）でした。

**原因**: GitHub Actions の runner は `unshare` が在っても namespace を
作れません。fail closed の Sandbox が生成物の実行を拒否し、build が走る
前提の既存試験が落ちました。**自分のホストでしか確かめていなかった**のが
原因です。

**直し方**: 「CI だから素通し」にはしませんでした。代わりに
`policy-only`（Policy 層だけ）という段を明示的に作り、

1. 既定は拒否のまま（`FORGE_SANDBOX_ALLOW_POLICY_ONLY=1` の明示が要る）
2. Evidence に `sandbox_backend="policy-only"` と**名前を残す**（OS 層と混ぜない）
3. 空文字にしない（空は「隔離せず走った」の意味で別物）

CI はこの変数を立てて走ります。**利用者の端末では変数が無いので拒否されます。**

なお **3 度落としました**。3 度目は別の原因で、`RLIMIT_AS`（仮想アドレス
空間）の既定 512MB が **Dart VM の起動時予約に足りなかった**ことでした。
Sandbox が拒否したのではなく、Sandbox の中で Dart が立ち上がれませんでした。
手元では Python の小さな subprocess でしか試していなかったためです。
2GB の仮想領域を予約するだけのプログラムで実測して確認し
（512MB → 失敗 / 8GB → 成功）、`SandboxPolicy.for_toolchain()` を足しました。
**緩めましたが外していません**（どの上限も有限であることをテストで固定）。

1〜2 度目は同じ原因でした。1 度目（`33812200098`）は backend job、2 度目
（`33812952355`）は frontend job の「生成 Dart の実ビルド経路」step です。
opt-in を step ごとに書いていたため、別 job の step に付け忘れました。
**「step を足すたびに思い出す」設計は忘れられます**——2 回連続で忘れたので、
workflow 全体の `env:` へ 1 箇所だけ置き直しました。

`unshare` を失敗する stub に置き換えて CI 環境を手元で再現し、
opt-in あり（794 passed / 24 skipped）と opt-in なし（9 failed = 拒否が
効いている）の両方を確認しました。

### まだ言えないこと

**Windows に Sandbox はありません。** だから「Sandbox 完成」とは書きません。
`99_PROVEN` は **0 件**です。能力差 0・121項目 99%・Z12 完了は宣言しません。

新規 TD110〜TD114。

詳細: `docs/reports/FORGE-SANDBOX-AND-CAPABILITY-ASSESSMENT-20260904-report.md`

---

## 121能力 Gap Matrix と Evidence 整合性（2026-09-03）

Base HEAD `61a199d` から実装した。

### やったこと（3つ）

1. **121 能力を機械が読める台帳にした。**
   `docs/evidence/capability_matrix/capabilities.json`（121 件、Target
   Contract は戦略 §2.5 をそのまま取り込み）。
   `scripts/check_capability_matrix.py` が CI で走り、**書けるより高い状態を
   主張していないか**を検査する。

2. **実 Provider 誤爆を Architecture で禁止した。**
   `backend/app/ai/gateway/external_call_policy.py`。Default Deny。
   **API キーの存在を同意として扱わない**——これが 2026-09-02 の事故の形。

3. **TD104 を解消した。** 呼んでいない Provider の名前を Evidence へ書かない。
   `backend/app/ai/gateway/model_call_ledger.py` が、configured（指定）と
   actually used（実際に答えた）を分けて持つ。0 回なら `"none"`。

### 121 能力の状態（2026-09-03）

| Status | 件数 |
|---|---:|
| `NOT_ASSESSED`（今回見ていない） | 102 |
| `NOT_STARTED`（見た。実装が無い） | 2 |
| `PARTIAL` | 5 |
| `IMPLEMENTED` | 12 |
| **`99_PROVEN`** | **0** |
| **`HARD_GATE_PROVEN`** | **0** |

**102 件を `NOT_ASSESSED` のまま残した**のは、121 を 1 セッションで正しく
評価できないからです。「見ていない」を「無い」と書くのも嘘なので分けました。

### ADR-015: 生成 Source は Drift ではなく Gate 付き Evolution

`docs/adr/ADR-015-generated-source-is-evolution-not-drift.md`

Constitution §8 の `controlled synthesis`、§10 の `promotion gates` が
生成 Source を予定しており、GEN-09/10/11・EXT-04/06 は Typed IR だけでは
満たせない。したがって **JSON-only へ戻すのは能力を削ることになり、選べない**。

すでに閉じている Gate: 隔離生成 / Digest 固定 / 静的解析 / 生成テスト /
実 Build / Runtime probe / Validator 語彙拡張の制限 / 出荷物の空検査。
**AI が書いた Source がそのまま Production へ入る経路は現時点で無い。**

**閉じていない Gate: Sandbox・Permission Manifest・Tier 強制・依存 allowlist。**
生成物の test/build を**ホスト権限**で実行しています。
そのため EXT-08 を `NOT_STARTED` へ、EXT-03 と AI-06 を `PARTIAL` へ
**下げました**（実態に合わせて下げた、という意味です）。

### 次にやるべき Gap（波及順、上位 3）

1. **Sandbox（EXT-08）** — 無いまま Self-Extension が動いている。SEC 全体が依存
2. **Frozen Final Holdout の運用** — 無いとどの能力も `99_PROVEN` に到達しない（CEO 決定待ち）
3. **Outcome 指標の Episode 収録**（Repair / p95 / RAM 等）— 99% の裏で性能が
   落ちていないことを示す唯一の手段

### 検証

- `pytest backend/tests`: **2066 passed / 16 skipped**（前回 2035）
- `pytest forge_ai/tests`: **747 passed / 10 skipped**
- `flutter analyze --fatal-infos --fatal-warnings`: No issues found
- `flutter test`: **589 passed**
- `check_universal_quality_policy.py`: PASS / `check_capability_matrix.py`: PASS
- 配線破壊試験 5 種 + Matrix 水増し 7 種、**すべて検出**
- **Real Provider calls: 0 件**（Default Deny により構造的に 0）
- **Real Local Model runs: 0 回 / Human Evidence: 0 人**
- **CI run `33701168608` @ `6bee221` — success、4/4 job、53 step すべて
  success（skip 0）。** 新設した「121能力Matrixの主張整合性を検査」step は
  Python 3.11 / 3.12 の両 job で実行され success（skip ではない）。
  https://github.com/hs9cghkmpw-alt/forge/actions/runs/33701168608

### まだ言えないこと

**「能力差 0 達成」「2億円版と同等完成」「全体 99% 達成」とは書けません。**
今回縮んだのは能力差ではなく、**差を測れない状態**です。

詳細: `docs/reports/FORGE-121-CAPABILITY-GAP-AND-EVIDENCE-INTEGRITY-20260903.md`

---

## Provider 非依存 UI と Core UX の正直さ（2026-09-02）

Base HEAD `5c4ce86` から実装した。**文言だけでなく構造を変えた。**

### やったこと

- ホーム画面の `_ProviderToggle`（`Gemini` ⇔ `Mock` をタップで切り替える
  ピル）を**削除**した。Provider 名を通常利用者へ見せない（Constitution
  §4・§9）だけでなく、**利用者に AI 経路を選ばせない**。片方の選択肢が
  疑似データだったという点でも二重に方針違反だった。
- 代わりに `AiModeIndicator`（**押せない**状態表示）を置いた。通常は
  `AIモード`、応答待ちは `AIが考えています…`、疑似データは `お試しモード`、
  接続不能は `AIに接続できません`。**表示は実状態に従う**。
- 開発者向けの Provider 指定は `--dart-define=FORGE_DEVELOPER_MODE=true`
  でビルドしたときだけ出る。既定ビルドには存在しない。
- Backend: `exception_handlers.py`（利用者向け文言が通る唯一の場所）で
  Provider の身元を含む文言を Provider 非依存文言へ差し替える。
  `_no_provider_message` からも「別の AI Provider を設定してください」を
  外した。**内部の `exc.message`・ログ・Evidence は実 Provider 名を残す。**

### 実描画で見つけて直した、2つの嘘

`flutter analyze` も Widget Test も通っていたが、実際に Chromium で
動かすまで気付けなかった。

1. **疑似データが `Generated by Forge` と名乗っていた。**
   `MockConversationRepository` が `simulated: true` を付け忘れており、
   `USE_MOCK_GENERATION=true` ビルドでは疑似データが実 AI の生成物と
   同じ見た目で表示されていた。Repository 側を直したうえで、
   `isSimulatedOutput()` が**ビルド自体の事実を必ず OR する**ようにした
   （「呼び出し側が忘れずに付ける」設計は忘れられる）。
2. **TD92 解消**: `ForgeFallbackWidget` が Release で `SizedBox.shrink()`
   を返し、描けなかった部分が黙って消えていた。Release でも必ず
   「この部分はまだ表示できません」を描く。内部語彙（Widget type 名・
   例外文字列）は出さず、debug ビルドでだけ技術的理由を出す。

### 検証

- `flutter analyze --fatal-infos --fatal-warnings`: No issues found
- `flutter test`: **589 passed**（変更前 562）
- `pytest backend/tests`: **2035 passed / 16 skipped**
- `pytest forge_ai/tests`: **747 passed / 10 skipped**
- `scripts/check_universal_quality_policy.py`: PASS
- `flutter build web --debug --no-web-resources-cdn`: ✓ Built
- Chromium 実描画 4 viewport（1440 / 820 / 390 / 320）:
  `docs/evidence/visual/provider-independent-ui-20260902/`
- 配線破壊試験 5 種すべてで対応テストが FAIL（置物ではない）
- **CI run `33694222382` @ `ce50d4d` — success、4/4 job、51 step すべて
  success（skip 0）。**
  https://github.com/hs9cghkmpw-alt/forge/actions/runs/33694222382

### まだ実証していない（達成済みと書かない）

- 実 Local Model での実機確認（このコンテナに Ollama が無い）
- `unavailable` / `preparing` の実描画（Backend 起動が要り、上記事故のため
  このホストでは起動しない）
- Mobile / Tablet の**実端末**（Chromium の viewport 再現のみ）
- Universal Quality 全体、121 項目 99%（今回の範囲外）
- 音声入力と文字入力の完全な等価性

### 新規 TD

- **TD104**: 呼んでいない Provider の名前を Evidence が名乗る。fast path
  （LLM 0 回）でも応答の `provider` が `"gemini"` になる場面を実機で観測した。
  表示はしていないので UI の問題ではないが、Evidence の正確さの問題である。

詳細: `docs/reports/FORGE-PROVIDER-INDEPENDENT-UI-20260902-report.md`

---

## 全方針の厳格監査とUniversal Quality固定（2026-09-02）

CEOの過去方針、添付構想、Constitution、Product Direction、Local AI Vision、
0円・全項目99%戦略を照合し、端末性能差が製品品質差へ漏れる記述を修正した。

- 新しい正本: `docs/architecture/FORGE-UNIVERSAL-QUALITY-INVARIANT.md`
- 監査報告: `docs/reports/FORGE-POLICY-ALIGNMENT-AUDIT-20260902.md`
- 憲法変更提案: `docs/reports/FORGE-CONSTITUTION-CHANGE-PROPOSAL-UNIVERSAL-QUALITY-20260902.md`
- 機械Gate: `python3 scripts/check_universal_quality_policy.py`

固定した原則:

- PC、GPU、RAM、OS、端末、無料・有料、Local・別Hostを品質Tierにしない。
- 全Profileへ同じTask、Visual、Safety、Privacy、Recovery、Accessibility Gateを適用。
- 変えてよいのは実行場所、Runtime、分割方法、消費資源、公開上限内の待ち時間。
- 最小限の道具は合意したScopeの段階化であり、品質縮小や無断の意味削除ではない。
- 未対応Capabilityを黙って消した低品質生成物は成功に数えない。
- 音声/文字、Mobile/Tablet/Desktop/Web、Navigation/History/Retry等のCore UXも
  横断Hard Gateにした。

`FORGE-SELF-CONTAINED-DISTRIBUTION.md`の`Low resource PC -> 小型モデル`は、
Reuse/CPU最適化/分割実行/許可済み別Hostへ修正した。Local Model Policy、
Machine-independent Policy、Agent pre-work checklist、0円戦略のLOC-10/11、Z2/Z9、
Q081/Q083/Q144/Q208/Q230も同じ方針へ統一した。

TD92の製品判断は確定した。releaseで無言消失を維持せず、未対応/修復中を正直に
示し、能力獲得・修復・戻るActionを提供する。低品質な代替生成物を成功表示しない。
Runtime修正そのものは次の実装Taskで行い、実RenderとVisual Evidenceを必須にする。

このTaskは方針・計画・CI Guardの修正であり、端末間同一品質の実製品Evidenceを
達成済みとはしていない。Z2/Z9/Z12で実証する。

CEOは提案の正確な英文と日本語の意味を確認後、「いいよ、すべて承認」と回答した。
その承認に基づき、Universal Quality InvariantをConstitution §13へ正式追記した。

---

## 0円・能力差0の実行戦略を設計（2026-09-02）

追加資金0円のまま、以前の2億円完成想定と**観測可能な製品成果を同じにする**
戦略を、次へ保存した。

- `docs/reports/FORGE-ZERO-BUDGET-ZERO-GAP-STRATEGY-20260902.md`

重要な境界:

- Reviewを反映し、Targetを **全121詳細能力それぞれ99%以上**へ更新した。
  AI理解10、生成14、Self-Extension 14、Local AI 11、学習13、UI 14、QA 12、
  Security 10、製品化15、Performance 8を個別Gate化した。各部品の
  点推定ではなく、Primary→Repair→Independent Fallback後に、同一Episodeで
  TC-01〜12を全て通したEnd-to-End成功率の95%信頼下限である。
- 10大分類も配下121項目が全てPASSした場合だけ合格。平均点で弱い項目を
  相殺せず、`UNKNOWN`、`SKIP`、標本不足、古いEvidenceは未達とする。
- 主要Sliceは原則400件以上、総合10,000要求、Human Calibrationは異なる
  初見参加者400人以上。同一人物の複数Taskを独立標本にせず、各Sliceも個別に
  下限99%以上でなければならない。
- Capability Tier A/B/Cを固定し、Tier Cは無承認自動実行ではなくPermissionと
  Human Gateを含む安全完了として採点する。意味削除・無言代替・単純拒否を
  Task成功に数えない。
- 現行のTemporary WorkspaceはSecurity Sandboxの証明ではない。Z5はSource
  AST/Import、Network/File/Process/Environment、CPU/RAM/時間の隔離とSandbox
  escape suiteを必須とする。
- Route Aは機械Gateの正本、Route BはHuman/Physical Closeoutの必須経路。
  PWAはClient、Local Model/BuildはNative Execution Hostとして分離する。
- 72時間SoakはGitHub-hosted Job一回へ載せず、既存PC/Self-hostedでCheckpoint
  付き実行する。AttestationとWindows SmartScreen reputationも分離した。
- 以前の `46.8 → 94.5` は実在する2億円版Binaryの実測ではなく成熟度推定。
  今後の差0判定は `TC-01〜TC-12` のTarget Contractで行う。
- 12能力面、Hard Gate、10,000未見要求、実機/Visual/Security/Recoveryを含め、
  一項目でも不足すれば差0にしない。
- 0円置換は、Automation / OSS / Reuse-first / Local Model / 公開CI /
  無償実端末枠 / 既存端末 / 分散Evidenceで行う。無償枠は必須依存にしない。
- Route A（単一Repositoryの自動証拠工場）を正本、Route B（分散Evidence
  Network）をHuman/Physical Closeoutの必須経路とする。
- 疑義を **256件**、16分野から列挙し、全件へ改善策と閉鎖Evidenceを割り当てた。
- Roadmapは `Z0〜Z12`。最初はTruth Lock、Physical Chrome、実機Stage timing、
  TD92/95/96/97/98/99の順に現在の具体的な穴を閉じる。

**この文書の状態はDESIGNEDであり、能力差0を達成済みとはしていない。**
能力差0を名乗れるのはZ12で全Target Contractを同一Release Candidateが
3回連続で通した時だけである。今回は製品Codeの挙動を変更していない。

---

## 直近の作業（2026-08-31 / FORGE-020F）

### やったこと

CEO 指示の最優先項目
**「acquired capability → Validator → real Flutter/Dart runtime」** に着手し、
**前半（Validator）だけを閉じました。後半（Dart）は閉じていません。**

* `backend/app/ai/validators/runtime_attested_widgets.py` を追加。
  **PROMOTED かつ loaded な BUILD_TIME activation を持ち、出力宣言を持つ**
  能力の widget 型だけが、Validator（生成物を検査する仕組み）の許可集合を
  広げます。`requested`（欲しいと言っただけ）でも `DECLARATIVE` でも
  広がりません。既定は空集合＝**忘れても緩まない向き**。
* `schema_validator.py` の実バグを修正。全版の出荷表を先に見ていたため、
  獲得型は許可集合へ足しても手前で「未知の widget」として落ちていました。
* 配線破壊試験（配線を1本ずつ外して対応テストが落ちるか確かめる）を **9件**
  実施し、**9件すべて検出**。初回は4本が素通りした（＝置物テストだった）ため、
  install 後に activation を壊す test class を追加してから再測しました。

### 今の状態

| 区間 | 状態 |
|---|---|
| acquired capability → Validator | **CLOSED**（14 tests + 破壊試験 9件） |
| Validator → 実 Flutter widget runtime | **CLOSED**（7 tests + 破壊試験 4件） |
| 生成 Dart → 実 `dart` で試験・解析・起動確認 | **CLOSED**（9 tests + 破壊試験 4件） |
| **生成 Dart → Forge アプリへ載せて実描画** | **CLOSED**（TD94。7 tests + 破壊試験 7件） |
| 実 Model が実装を書く / 実機 Chrome 表示 | **NOT CLOSED**（TD95） |

### 途中で見つけたこと（実 Flutter で実行して確認）

* 獲得 widget は Parser の `switch` で `ForgeUnknownWidgetNode` へ倒れ、
  **Registry へ登録しても描かれませんでした。** 拡張点は Registry ではなく
  **Parser 側**でした（**TD93**）。Registry を拡張点だと思って作業すると
  必ず外すので、まずテストで固定してから穴を開けました。
* `ForgeFallbackWidget` は release build では `SizedBox.shrink()`。
  描けない widget が**無言で消えます** → **TD92**。2026-09-02のCEO方針で
  無言消失は禁止と決定した。実装修正とVisual Evidenceは次Task。

### Dart 側に開けた受け口

`frontend/lib/json_ui/schema/acquired_widget_types.dart`。
獲得能力の生成コードが、載るときに**2つとも**自分で登録します。

1. Parser 側の宣言（型名と必須 property）
2. Widget Registry（実際の描き方）

**片方だけでは描きません。** 描けないものを描けたことにしないためです。
Forge 本体に `if capability_id == ...` の分岐は**ありません**。

### 検証結果

```text
backend        1998 passed, 16 skipped
forge_ai        717 passed
ruff (変更箇所)  All checks passed
flutter analyze No issues found
flutter test    557 passed（546 → 550 → 557）
forge_ai(dart)  9 passed（FORGE_REQUIRE_DART_BUILD=1、実 dart subprocess）
配線破壊試験      backend 9件 / Dart 4件 / build plan 4件 = 17件すべて検出
```

Evidence: `docs/evidence/ACQUIRED-CAPABILITY-VALIDATOR-BOUNDARY-20260831.md`
ログ: `logs/forge-020f-guard-break-20260831.log`、
`logs/forge-020f-dart-guard-break-20260831.log`、
`logs/forge-020f-dart-plan-guard-break-20260831.log`

### CI（canonical）

run **33387417433** / head `442ba87` / **4 jobs すべて success**。

新しい step「生成 Dart の実ビルド経路」は frontend job の step 8 として
**実際に走って success** しています（skip ではありません——
`FORGE_REQUIRE_DART_BUILD=1` は dart が無ければ失敗させます）。

### どこまでを「閉じた」と言っているか（過大主張の防止）

閉じたのは**実 Flutter widget runtime**まで（`flutter test` は本物の Dart VM と
widget tree を動かします）。

**言っていないこと**:
Chrome 上の Forge アプリで自律生成能力を描いた ——**していません**。
本番起動経路へ架空の capability を登録するのは偽装なので行いません。

### Dart の build plan も足しました（TD94 の半分）

生成された Dart が**本物の `dart`** で試験・静的解析・起動確認を通ることを
実 subprocess で確かめています（`tests ok` / `runtime probe ok` が実際の
出力に出ることまで見ています）。テストが落ちる／解析が通らない／probe が
落ちる、のいずれでも PROMOTED されません。

ついでに実バグを1件直しました。Python の手順は `probe.py` を名指しで
実行しながら、**その名前を生成側へ要求していません**でした。名前が違えば
コマンドがファイル不在で落ち、**生成の失敗が build の失敗に化けます**。

**CI で skip させない工夫**: Python の job に `dart` は無いので、この経路は
あちらでは skip されます。skip されたテストは何も証明しないので、
`dart` を持つ frontend job で走らせる step を足し、
`FORGE_REQUIRE_DART_BUILD=1`（dart が無ければ skip ではなく**失敗**）を
立ててあります。

---

## 段ごとの実測を入れました / 実機計測はお願いです（2026-09-01 追記）

### まず、前回の私の言い方を訂正します

**73.54 秒 → 0.09 ミリ秒は Forge 全体の時間ではありません。**
最初の「聞くか作るか」を決める判定が、LLM 0 回になった結果です。
そのあと画面を作る時間は**まだ測っていません**。倍率で言うと全体が
速くなったように読めるので、以後は倍率で言いません。

**`Real Local Model runs = 0` は「Local Model を動かしていない」という
意味ではありません。** 実モデルによる会話経路は実機 PASS 済みです。
0 なのは、実 Local Model が**新 Capability を生成 → 検証 → 取り込み →
再利用まで完走した回数**です。

### 入れたもの

段ごとの実測を**本番経路そのもの**で取り、`/converse` の応答へ
`timings` として返すようにしました。

| 出るもの | 中身 |
|---|---|
| 段ごとのミリ秒 | 速い道の判定 / 会話ステップ / 会話の LLM / 生成 / Validator |
| 回数 | 会話の LLM 呼び出し / 生成の実行 / Validator |
| 事実 | 速い道を通ったか、その理由 |

配線破壊試験 7件すべて検出（測るのを止める・応答へ載せない、等）。

### この環境で確かめたこと（**実モデルではありません**）

**Ollama はこのコンテナにありません。実機の数字は私には取れません。**
確かめたのは「計測が本番経路で動き、段が分かれて返ること」だけです
（`provider=mock`）。

### 実機でお願いしたいこと

Backend を起動した状態で、**1コマンド**です。

```bash
python3 scripts/measure_real_device_converse.py
```

2件を投げて、段ごとの実測をログへ残します。

1. 「事務所の鍵を誰が持ち出していて、いつ返す予定なのか記録できるようにしたい」
   → **status=build** になり、記録項目を聞き返さないこと
2. 「家族で予定を管理したい」
   → **雑に BUILD せず、聞けること**

**遅かったら timeout を伸ばさないでください。** script が一番遅い段を
名指しします。そこを速くします。

### そのあと Chrome（人が見る）

上の2文を Chrome から入力し、**画面が出るところ**と**聞き返すところ**を
人が見てください。**見ていないものを PASS にしません。**

### 配布方針を読みました

`FORGE-SELF-CONTAINED-DISTRIBUTION.md` と
`FORGE-LOCAL-MODEL-QUALITY-AND-QUANTIZATION.md` を今後の前提とします。
利用者に Ollama / Python / PowerShell を要求しない、容量のために品質を
落とさない、量子化は比較検証の候補、を守ります。

---

## 実機の失敗を直しました（2026-09-01）

### 実機で分かったこと（丸めません）

| | |
|---|---|
| Local Model 接続 / HTTP 200 / `simulated=false` | **PASS** |
| 応答時間 73.54 秒 | **FAIL** |
| 意味判断 | **FAIL** |
| Chrome 完走 | **FAIL** |

「事務所の鍵を誰が持ち出していて、いつ返す予定か記録したい」に対して、
**記録項目を「聞くべき未知」と誤判定して聞き返していました。**
「誰が」「いつ返す」は未知ではなく、作る道具の入力欄です。

### 原因

**reuse-first B は本番の入口へ繋がっていませんでした。**
`ConversationEngine.step()` は判定の前に**無条件で**大きな prompt と schema を
小型モデルへ渡していました。そこが 73 秒です。

### 直したこと

会話の入口の手前に、**決定的に決められるなら LLM を呼ばない**層を置きました。
判断には**既存の資産だけ**を使っています（capability decomposition と
risk 検出）。新しい分類器も別系統も作っていません。

**迷ったら速い道へ倒しません。** 足りない能力がある / 外部作用や不可逆操作の
気配 / 本当に曖昧 / 対象が名指しされていない / 複数人で使う前提 /
既存物への変更 / 2ターン目以降、はいずれも従来どおり LLM へ渡します。

### 実測

| | Before（実機） | After |
|---|---|---|
| 応答 | **73.54 秒** | **0.09 ミリ秒** |
| LLM 呼び出し | 1 回 | **0 回** |
| 判定 | **ASK（誤り）** | **BUILD** |

曖昧な文（「なんとかしてほしいんだけど」等）は**ちゃんと ASK**、
足りない能力がある文は**ちゃんと名指し**します。速さのために雑にしていません。

再現: `python3 scripts/converse_fast_path_e2e.py --seed 20260901`

### 途中で Golden が2件落ちて、設計を直しました

「家族で予定を管理したい」「家族で何か管理したい」は**聞くべき未知**です。
テストを緩めず、速い道の規則の方を直しました。

### Flutter の待ち時間

`receiveTimeout` を 10 秒 → 60 秒にしました。**これは主たる直しではありません。**
主たる直しは判定を速くしたことです。生成段の実時間は別に測ります（TD98）。

### 実機で次に確認していただきたいこと

1. `/converse` へ同じ文を `provider=local` で POST → **応答時間**と `status`
2. 生成まで含めた**実時間**（60 秒で足りるか）
3. Chrome から同じ文 → **画面まで到達するか**
4. 「家族で予定を管理したい」→ **ちゃんと聞き返すか**

### CIを2回落としました（どちらも同日中に修正）

**どちらも速い道の不具合ではありません。私の手順ミスです。**

| run | SHA | 落ちた場所 | 原因 |
|---|---|---|---|
| 33469325234 | `e3c4a34` | `flutter test` 48件 | 獲得物を出荷物と一緒に commit した |
| 33470175316 | `0d5415e` | 会話E2Eのstep | script の置き場所を間違えた |

**1回目**: 回帰確認でE2Eを走らせたまま commit し、獲得能力を指す登録表を
出荷物に混ぜてしまいました。獲得したDart本体は commit しない設計なので、
新しいcheckoutでは存在しないファイルをimportする状態になりました。

**2回目**: 会話入口の速い道を測る script を **frontend job** へ置きました。
あのjobには Flutter しか入っておらず `backend/requirements.txt` がありません。
script は `ConversationEngine` を import し、そこから `httpx` まで辿ります。

```text
ModuleNotFoundError: No module named 'httpx'
```

手元では依存が全部入っているので通っていました。Flutterもdartも要らない
試験なので、**置き場所そのものが誤り**でした。backend job へ移しました。

### 同じ失敗を機械に見させるようにしました

「commit前にrestoreするのを忘れない」「どのjobに何が入っているか覚えておく」
——**まさに私が忘れたこと**です。両方ともテストにしました。

| テスト | 見るもの |
|---|---|
| `test_shipped_acquired_registrations.py` | 出荷する登録表が空か / import先が実在するか / 獲得物が残っていないか |
| `test_ci_job_dependencies.py` | frontend job が呼ぶ script が backend の実装を import していないか / CIが呼ぶscriptが実在するか / 速い道のstepが消えていないか |

どちらも**CIを落とした状態を再現すると落ちる**ことを確認しています。

Evidence: `docs/evidence/CONVERSATION-FAST-PATH-20260901.md`

CI: run **33471061839** / head `d34ffd6` / **4 jobs すべて success**。
会話入口の速い道の step は backend job で実際に走っています（skip なし）。

---

## 方式B を本線にしました（2026-08-31 / 同日 追記）

### 簡単に言うと

* **持っている能力だけで作れる要求は、新しいコードを1行も作らずに即表示**します（0.4 ms）
* **足りない能力があるときだけ、その1つだけを作ります**（1062 ms。ほとんどが「本当に動くか確かめる」時間）
* **一度作った能力は次から作り直しません**（0.2 ms。約 5000 倍速い）

### 直した実バグ

TD94 の E2E は、**検査した生成物とは別にもう一度生成して**それを Flutter へ
載せていました。検査した対象と動く対象が別物です。いまは1回だけ生成し、
検査を通ったそのものを載せます。`install()` は検査済みの型しか受け取らず、
直前に digest を照合するので **1byte でも変われば落ちます**。

### ランダム自由文で見つかったこと（TD96）

固定文をやめた瞬間、**要求を読み取れない言い回しが出てきました**。
「月ごと」「出勤した日」が読めていませんでした。2つ直しましたが、
月表示の要求の読み取り率は **117/200** のままです。
取りこぼした文はログへ残しています（無かったことにしません）。

### 実測（seed 20260831）

| | 入力文 | 生成 | 所要 |
|---|---|---|---|
| A | うまく言えないけど、釣れた魚を残しておいて、釣れた場所も一緒に並びにしたい。 | **0 回** | 0.4 ms |
| B | 働いた時間を記録して、出勤した日を月ごとにまとめて見たい。 | **1 回** | 1062.1 ms |
| C | 出した書類を記録して、出した日を月ごとにまとめて見たい。 | **0 回** | 0.2 ms |

再現: `python3 scripts/reuse_first_e2e.py --seed 20260831`

Evidence: `docs/evidence/REUSE-FIRST-B-20260831.md`

CI: run **33447252973** / head `85e50b7` / 4 jobs すべて success。
自由文 E2E の step も **skip なしで実行**されています。

### 次にやること

1. **実機 Chrome 表示**（獲得を載せた状態で撮る）
2. **TD97**: 獲得した能力の再利用が process ローカル。再起動しても
   獲得済みのままかは未確認
3. **TD96**: 要求理解の取りこぼし。語を足す方向では埋めない

---

## TD94 を閉じました（2026-08-31 / 同日 追記）

### 何が繋がったか

```text
未知の要求
  → Capability Plan が gap を名指しする      （view.calendar が missing）
  → 実装を生成する                            （Dart）
  → 隔離 workspace で実 dart による試験・解析・起動確認
  → PROMOTED
  → Forge の Flutter アプリへ install          ← ここが空いていた
  → 本番 compiler が生成 Document へ widget を出す
  → Parser → document model → Registry → 実 Widget
```

CEO が挙げた10項目はすべて PASS です（内訳は Evidence の §2）。

### 設計の要点

* 獲得能力は **Parser 側の宣言と描き方を両方**持ちます。片方だけの値は
  型として作れません（`ForgeAcquiredCapability`）。
* 登録は**本番が必ず通る2箇所**から呼ばれます——Parser が未知の型を見たとき、
  Registry を組むとき。「呼び出し側が忘れずに呼ぶ」設計にしていません。
* installer は登録表を**丸ごと作り直します**（追記ではない）。installer を
  通っていない能力が表に残り続ける形にしていません。
* 生成物は **commit しません**。commit すると「出荷済み source」になり、
  生成したものと出荷したものの区別が消えます。CI が毎回作り直します。

### 途中で直した実バグ 2件

1. Parser の獲得分岐が `json['properties']` を読んでいましたが、生成
   Document は属性を**平ら**に持ちます。獲得 widget が**永久に parse で
   落ちていました**。
2. 「表が空である」を期待するテストは、実際に能力を獲得した checkout で
   **獲得を壊れたことにしてしまいます**。「この型が入っていない」へ変更。

### 置物テストを1本見つけて潰しました

配線破壊試験の T2（Registry 側の登録呼び出しを外す）が**初回は素通り**
しました。同じファイル内で先に走ったテストの parse が既に登録を済ませて
いたためです。parse を一切しない独立ファイルを足して締め直しました。

### 検証結果

```text
flutter analyze  No issues found（獲得を載せた状態）
flutter test     562 passed（素の状態）
flutter test test_acquired  7 passed（獲得を載せた状態）
flutter build web  ✓ Built build/web（獲得を載せた状態）
forge_ai         736 passed
backend          1998 passed, 16 skipped
配線破壊試験       TD94 7件すべて検出（累計 24件）
```

Evidence: `docs/evidence/TD94-ACQUIRED-CAPABILITY-IN-THE-FLUTTER-APP-20260831.md`
ログ: `logs/forge-td94-e2e-20260831.log`、`logs/forge-td94-guard-break-20260831.log`

### CI（canonical）

run **33409772751** / head `a89ea7f4cc93a803efb28098edadf6555db2e60c` /
**4 jobs すべて success**。

frontend job で TD94 の step が**実際に走って success**しています
（skip ではありません）。

| # | step | 結果 |
|---|---|---|
| 8 | 生成 Dart の実ビルド経路 | success |
| 9 | 獲得 Capability を Forge アプリへ載せる | success |
| 10 | flutter analyze（獲得を載せた状態） | success |
| 11 | flutter test（獲得 Capability が実際に描かれる） | success |
| 12 | flutter build web（獲得を載せたまま） | success |


### 次にやること

1. **実機 Chrome 表示**（CEO の指示どおり、TD94 の次）。この Linux ホストで
   `flutter run -d chrome` は既に成功しているので、獲得を載せた状態で
   撮ります。
2. **TD95 の残り半分**——実 Model が capability の実装を書いた証拠。
   **Real Local Model runs = 0 のまま**です。
3. ぱすとらる PC の Puro 問題（CEO 依頼 2）。

### まだ証明していないこと（推測で埋めない）

* Real Local Model が capability の source を書くこと（**Real Local Model runs = 0 のまま**。Provider は Test Double）
* 実機 Chrome での自律生成能力の描画
* 自然言語の要求から Capability 契約を機械的に引くこと（いまは script が固定）
* ぱすとらる PC での `flutter run -d chrome` 成功

---

## Canonical product invariant

Forge's goal has **not switched** to a new mode or to a finite app-coverage program.

> **持っている能力は組み合わせる。足りない能力は作る。作った能力は検証し、再利用可能な Forge Capability として取り込む。**

Everything else—Golden apps, widgets, GA phases, schemas, runtime primitives, local models, benchmarks—is an implementation mechanism or test surface under that invariant.

Canonical hierarchy:

1. `docs/FORGE-CORE-CONSTITUTION.md`
2. `docs/PRODUCT-DIRECTION.md`
3. `docs/GENERATIVE-SOFTWARE-DIRECTION.md`
4. `docs/LEARNABLE-LOCAL-AI-VISION.md`
5. `docs/FORGE-CURRENT-STATE.md`
6. this handoff

Operational scan term:

- **全体スキャン / Whole Scan** = `docs/FORGE-WHOLE-SCAN-PROTOCOL.md`

## Current branch / active engineering slice

- Branch: `claude/forge-master-handoff-k46jns`
- Active slice: self-extension production loop + GA-1 logic closure.
- Execution program: `docs/spec/FORGE-GENERAL-APP-MODE.md`.
- Self-extension basis: `docs/spec/FORGE-SELF-EXTENSION-ARCH-REVIEW-v2.md`.

`FORGE-GENERAL-APP-MODE.md` is **not a new product goal**. Missing-capability synthesis is cross-cutting and must not be postponed until the end of a phase list.

## Physical-PC checkpoint — 2026-08-31

A real Windows PC at ぱすとらる was used to continue Forge verification. The durable checkpoint is:

- `docs/evidence/PHYSICAL-EXECUTION-CHECKPOINT-20260831.md`

Observed session results:

- `flutter analyze`: **PASS / clean**
- `flutter test`: **PASS — 546 tests**
- `flutter build web`: **PASS**
- `flutter run -d chrome`: **BLOCKED before successful app startup**
- actual Chrome-rendered app: **UNVERIFIED**
- manual visual/behavioral interaction: **NOT EXECUTED**

Current physical blocker: Flutter SDK / web SDK path resolution through Puro. An observed path was shaped like:

```text
../../../.puro/envs/stable/flutter/bin/cache/flutter_web_sdk/
```

Important evidence boundary: the exact local checkout SHA used for that physical run was **not durably captured**, so the next session must run `git rev-parse HEAD` before attaching the physical results to a specific commit.

**Resume from here, do not repeat completed work by default:** start a PowerShell transcript, capture branch/HEAD and Flutter environment identity (`where.exe flutter`, `flutter --version`, `flutter doctor -v`), fix the Puro/Flutter SDK path issue, then rerun `flutter run -d chrome`. Only after the app visibly loads should physical runtime be marked PASS. After base startup succeeds, continue into the self-extension -> acquired capability -> real Flutter/Dart runtime path.

## Self-extension: what the build pipeline now actually proves (020E-2/3)

`SynthesizingBuildTimeImplementer` is the **production** `ExtensionImplementer`.
Until it existed, the only implementer ever injected into `extension_cycle` was
a test closure.

Proven with **real subprocesses** (no fake builder/loader):

```
test           python -m unittest discover   exit 0
build          python -m compileall -q .     exit 0
runtime_probe  python probe.py               exit 0   stdout: "runtime probe ok"
-> manifest promoted, promotion_blockers empty, activation loaded
```

Negative proof: a failing generated test, a failing probe, or source that does
not compile all leave the manifest **unpromoted with `activation is None`**;
later phases do not run after an earlier phase fails; an unsupported host
language is refused rather than defaulted to Python; regurgitated shipped
source raises `PreexistingSourceError`.

Capability prerequisites are now **declared in the canonical catalog**
(`CapabilityDefinition.required_fields`) instead of branching on a capability
name in the planner. The former `if "view.map" in directly_requested:` branch is
gone — an acquired capability could never have that branch written for it, so it
could never stand on its own. This is **not** permission to geocode: the map
capability declares explicit numeric latitude/longitude, and a place name alone
still produces no coordinate fields.

**Still unproven — do not read this as a completed self-extension E2E:**

| Item | State |
|---|---|
| That a **real model** authored the generated source | **UNPROVEN.** The provider here is a Test Double; the implementation string is supplied by the test |
| Natural-language request -> acquisition -> retry -> reuse | **PROVEN** (real build; `capability_plan` consults the registry on retry) |
| Acquired capability can contribute a widget to the generated document | **PROVEN at compiler/document-emission level.** Compiler capability-name branching is gone and a registered contribution can emit its widget through the production IR/compiler path |
| Validator PASS for a genuinely acquired/new widget | **UNPROVEN** |
| Flutter runtime rendering evidence for a genuinely acquired/new widget | **UNPROVEN** |
| Second different request reuses without a second build | **PROVEN** (synthesis=1, build=1, provider_calls=1 across two different requests) |
| Real model authorship runs for `capability_implementation` | **0** |

Evidence: `docs/evidence/SELF-EXTENSION-BUILD-PIPELINE-20260831.md`.

Next real bottlenecks — there are **two**, not one:

1. **Real model authorship.** Executing the `capability_implementation` stage
   against a real model. Plumbing and gates are in place; what is missing is a
   machine that can run one (`docs/MACHINE-INDEPENDENT-POLICY.md`).
2. **The acquired capability must be renderable by the Dart runtime.**
   The compiler-side `if "view.map"` branch is **now gone** (020E-5): widget
   emission is declaration-driven, and an acquired capability can register its
   own contribution, which was verified. `view.map` output is unchanged down to
   property order. What remains is that a declaration only says *which widget to
   emit* — whether the Dart runtime can **render** a genuinely new widget still
   requires rebuilding the Flutter side through BUILD_TIME. That is untouched.

   While doing this a coverage hole surfaced: removing the shipped map
   declaration left **all 1984 backend tests and all forge_ai tests passing**,
   i.e. the `view.map` emission path had never been tested at all. It is now.

## Determination: map so far is activation, not generation (020E, 2026-08-30)

Ordered explicitly by the CEO before any further self-extension work.

**`view.map` to date is activation of pre-existing shipped code, not
capability generation.** Evidence in repo:

- `BuildTimeCapabilityArtifact(...)` is constructed in **tests only**
  (3 sites); there is **no production construction site**;
- `ExtensionImplementer` is a Protocol; the only implementer injected is a
  test closure;
- `test_self_extension_loop.py` promotes `view.map` through
  `ExtensionRoute.DECLARATIVE` — **no source is generated**;
- the v1.16 map language/validator/parser/registry/runtime/compiler wiring
  was written by earlier human commits and shipped in the repo.

`ManagedBuildTimeImplementer` genuinely proves *verification and intake* of a
given artifact via real subprocesses. It does **not** prove that Forge wrote
the implementation.

Full record: `docs/reports/FORGE-020E-CAPABILITY-ARTIFACT-SYNTHESIS-report.md`.

## The generation stage is now present (but not yet proven end to end)

`forge_ai/core/orchestration/capability_artifact_synthesis.py` fills the gap
between Capability Gap and BUILD_TIME.

- capability-agnostic: takes only a contract pulled mechanically from the
  canonical catalog; a static test forbids capability-id literals in the
  executable code, so `if capability_id == "view.map"` cannot be introduced
  as the general mechanism;
- `known_source_digests` is a **required** argument: source that is
  byte-identical (after whitespace normalisation) to shipped source raises
  `PreexistingSourceError`, so regurgitated repo code cannot be counted as
  generation;
- unusable responses return `None` — implementation without tests, tests
  without implementation, empty output, unsafe paths;
- capability identity comes from the contract, never from model self-report.

**Still unproven:** real-model-authored unseen capability source -> real build/probe ->
PROMOTED -> retry -> real Flutter runtime rendering -> reuse without a second build.

## Self-extension implementation now present

The production architecture now contains these reusable stages:

```text
Capability Gap
 -> CognitivePipelineNeedsExtension
 -> ExtensionCandidate
 -> ExtensionManifest
 -> route-specific implementation
 -> evidence gate
 -> VERIFIED
 -> PROMOTED
 -> executable activation
 -> registry install
 -> original request retry
 -> repeated loop until all gaps close or progress stops
```

Implemented guardrails include:

- unresolved semantics cannot skip decomposition;
- unverified manifests cannot promote;
- sensitive capability promotion requires safety evidence;
- manifest-only promotion is insufficient: executable activation is required;
- BUILD_TIME capabilities require a loaded runtime/build attestation before reuse;
- capability identity may not change during implementation;
- the same unresolved gap after promotion is treated as no progress;
- retry cycles are bounded;
- promoted declarative capabilities can be persisted and integrity-checked on reload.

Relevant production surfaces include:

- `forge_ai/core/orchestration/extension_plan.py`
- `extension_manifest.py`
- `extension_activation.py`
- `extension_registry.py`
- `extension_cycle.py`
- `self_extension_loop.py`
- `declarative_extension.py`
- `declarative_activation.py`
- `extension_store.py`
- `build_time_extension.py`

The multi-gap regression in `forge_ai/tests/test_self_extension_loop.py` proves that a request needing more than one missing capability is not completed after acquiring only the first gap.

## GA-1 logic vertical slice

GA-1 is now wired through the generated document path rather than existing only as a standalone expression helper.

```text
Python GA-1 Logic model
 -> ForgeIRDocument.logic
 -> generated JSON `logic`
 -> Backend Validator
 -> Dart ForgeDocument parser
 -> ForgeLogicRuntime
 -> Renderer `visible_when`
```

Implemented reusable semantics:

- literal/state references
- arithmetic and comparison
- boolean composition
- aggregate operations
- derived values computed from current mutable state
- conditional widget visibility

Derived values are not copied into mutable state, so they do not create a second Source of Truth.

Validator behavior is fail-closed:

- `logic` is accepted only for Forge Language v1.15+;
- unknown expression kinds/operators are rejected;
- aggregate field references are constrained to their valid context;
- expression depth and logic-entry count are bounded.

Key commits:

- `2abf295132d3f83ced0f65863e651f5b24b37b1b` — deterministic expression engine
- `8dc9e38bab6aa38b0d6119282911422cfb4b1c86` — runtime state binding
- `ebe90998c321cbd886dbdbae8b486b641791e3a7` — document/parser/renderer GA-1 wiring
- `a83396ed3f7b1e21c48118a9c75d4049101db472` — backend GA-1 validator

## Whole Scan status

The first Whole Scan corrected the highest-risk strategic drift:

- legacy JSON-only/product-boundary wording was demoted;
- undefined requirements may not be rewritten into convenient templates;
- only an explicitly planned CHECKLIST may enter the legacy checklist compiler;
- unresolved RECORD_ENTITY / UNKNOWN structure becomes Capability Gap;
- Capability Gap is a first-class `CognitivePipelineNeedsExtension` outcome, not generic failure;
- `SolutionShape` is a downstream legacy representation chooser, not the product capability catalog;
- self-extension is evidence-gated and retry-oriented rather than a claim-only registry;
- stale comments/docstrings that still describe automatic checklist fallback are being removed as part of final scan cleanup.

See `docs/reports/FORGE-WHOLE-SCAN-20260830-report.md` for the full scan record.

## CI evidence

Canonical CI run `33340554937` on head `c2ec1529ce1c3eb97d456dc667a03cd1a3ee1ac7` completed successfully
(4/4 jobs):

- backend + forge_ai Python 3.11: PASS
- backend + forge_ai Python 3.12: PASS
- backend smoke: PASS
- Flutter analyze/test/web build: PASS

Earlier green heads in this slice: `33340416175` (`8ea7fc9d`), `33339800860` (`d8a9341`), `33339385724` (`83683e1`), `33339175463` (`5827f2d`),
`33338884887` (`2fba6f1`), `33328203164` (`8e3c876`).

A later HEAD must receive its own canonical CI before being called green.

## Existing Golden game closure remains valid

Previous Golden request:

> `植物を育てながら音を組み合わせるゲームを作りたい`

Durable evidence remains in:

- `docs/reports/FORGE-GOLDEN-GAME-CLOSURE-report.md`
- `docs/evidence/golden/forge-golden-game-closure-20260830.json`

Truth status remains:

- `simulate.loop`: IMPLEMENTED
- `interact.audio_mix`: PARTIAL
- `effect.media_compose`: MISSING
- physical/user-PC verification: UNVERIFIED

Do not treat that Golden as a template or as proof of general software-generation completion.

## Next engineering target after this scan pass

Do not expand patterns for their own sake. Continue from the real goal backward:

1. **Finish the current physical-PC startup checkpoint first:** fix the Puro/Flutter SDK path issue and get `flutter run -d chrome` to a visibly rendered app while preserving the transcript and exact Git SHA.
2. **Then prove one real unseen request end-to-end** through `Gap -> extension -> promotion -> retry -> working generated product`, including Validator and real Flutter/Dart runtime evidence.
3. Convert boolean extension evidence flags into stronger evidence references/artifact identities where practical.
4. Continue GA-2 persistent data/navigation and later capabilities only as reusable primitives.
5. Rerun Whole Scan whenever new capability routes or fallbacks are introduced.

## Final closure rule

A branch state is green only when persistent `.github/workflows/ci.yml` passes for that exact descendant HEAD. Pending/unmeasured evidence is never PASS.
