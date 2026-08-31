# Forge Handoff — current Source of Truth

---

## CEOへの依頼（最優先・上から順に）

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

3. **TD92 の判断。** 描けない widget が release build で無言で消えます
   （下記「今回の発見」参照）。現状維持か、可視 signal を出すか。

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
| 生成 Dart → Flutter アプリへ載せて実描画 | **NOT CLOSED**（TD94 の残り） |

### 途中で見つけたこと（実 Flutter で実行して確認）

* 獲得 widget は Parser の `switch` で `ForgeUnknownWidgetNode` へ倒れ、
  **Registry へ登録しても描かれませんでした。** 拡張点は Registry ではなく
  **Parser 側**でした（**TD93**）。Registry を拡張点だと思って作業すると
  必ず外すので、まずテストで固定してから穴を開けました。
* `ForgeFallbackWidget` は release build では `SizedBox.shrink()`。
  描けない widget が**無言で消えます** → **TD92**（製品方針に触るため
  勝手に変えていません。CEO 依頼 3）。

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
`logs/forge-020f-dart-guard-break-20260831.log`

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

### 次にやること

1. **TD94 の残り。** 隔離 workspace は Flutter を持たないので、生成 Dart を
   Forge の Flutter アプリへ組み込んでビルドし、上の 2 箇所へ登録させて
   **実際に描く**ところが未実装です。
2. それが繋がってから、Chrome 実機で撮る（この Linux ホストで可能）。
3. ぱすとらる PC の Puro 問題（CEO 依頼 2）。

### まだ証明していないこと（推測で埋めない）

* 生成された Dart を Flutter アプリへ載せて描くこと（TD94 の残り）
* Chrome 実機での自律生成能力の描画
* Real Local Model が capability の source を書くこと（**Real Local Model runs = 0 のまま**）
* 未知の要求からの完全 E2E
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
