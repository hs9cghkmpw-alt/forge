# FORGE-020A2 / GENERATED-UI-QG-V2-R5 — 実施報告

- Task: FORGE-020A2（CEO指示、2026-08-27）
- Branch: `claude/forge-master-handoff-k46jns`
- 前回: `FORGE-020A1-QG-V2-R4-report.md`（Reviewer 判定 **NO-GO**）
- 視覚 Evidence: `docs/visual-evidence/QUALITY-GATE-V2/round-5/manifest.md`

---

## 0. 結論

| 項目 | 結果 |
|---|---|
| §1 Capability SoT 統一 | 完了。正典は `forge_ai/core/semantics/capabilities.py` 1つ |
| §2 直交 CapabilityPlan | 完了。排他的 `PlanShape` を廃止、複数 view が同時に載る |
| §3 Structure Provenance | 完了。`GenerationStructureSource` を型で持つ |
| §4 CapabilityUsageEvidence | 完了。`GenerationRecord` へ記録（値・利用者文は入れない） |
| §5 TD90 Missing Capability の告知 | 完了。本番 HTTP 応答に `capability_gap` |
| §6 TD91 Semantic Layout Composition | 完了。専用 UI は1つも作っていない |
| §7 TD92 操作して撮る | 完了。**56枚 / 押せなかった操作 0件** |
| §8 機械非依存の方針 | 訂正済み。**GPU は Benchmark の前提条件ではない** |
| §9 Mutation M1–M14 | 全件、対応するテストが落ちることを確認 |
| **Golden Quality Gate** | **FAIL**（ゲームは今も CRUD フォームである） |
| **Real Local Model runs** | **0**（増やしていない） |

**020B production wiring は開始していない。**

---

## 1. Capability Registry の SoT を1つにした（§1）

### 何が2系統だったか

| 場所 | 持っていたもの |
|---|---|
| `forge_ai/core/semantics/capability_plan.py` | Need から出る Capability の語彙 |
| `backend/app/ai/runtime/capability.py` | supported / requires_confirmation / widget 対応 |

同じ Capability の「使えるかどうか」が**2箇所で手書き**だった。
片方だけ直せば静かにずれる。

### どう1つにしたか

正典を `forge_ai/core/semantics/capabilities.py` に置いた（31件:
IMPLEMENTED 14 / PARTIAL 3 / MISSING 14）。1件あたり
`id / layer / label_ja / intent / support / safety / detection_keywords /
nearest_supported_id / limitation` を持つ。

`backend/app/ai/runtime/capability.py` は **Runtime Capability Adapter**
になった。持つのは `_RUNTIME_BINDINGS`（capability id → widget type）
**だけ**である。

- `supported` は `SupportLevel` から**導出**する（手で書かない）
- `requires_confirmation` は `SafetyClass` から**導出**する
- `forge_ai` は `backend` を import しない（依存の向きは backend → forge_ai）
- 両者の整合は機械が検査する（`test_forge_020a2_capability_sot.py`）

> **名前だけ変えた二重表にしない**——`_RUNTIME_BINDINGS` に
> 正典に無い id が入ったら、または正典の IMPLEMENTED に binding が
> 無かったら、テストが落ちる。

---

## 2. PlanShape を直交成分へ（§2）

### 再現テストを先に書いた

「部署ごとの売上を比較して、合計と月別推移も見たい」——
排他的な `PlanShape` では**1つの Shape しか選べない**ので、
`metric` か `group_compare` か `trend` のどれかが黙って落ちていた。

### 直した形

```
CapabilityPlan
  structure      StructuralMode（record_entity / checklist / unknown）
  views          set                ← 複数同時
  interactions   set
  effects        set
  requested      set
  partial / missing
```

**不変条件**: `requested` にあるものは、必ず views / interactions /
effects / structure_capabilities / partial / missing の**どこかに現れる**。
これがテストで固定してあるので、「requested に入れたのに誰も見ていない」
が起きない。

実測（`plan_capabilities()`）:

```
部署ごとの売上を比較して、合計と月別推移も見たい
  views: view.group_compare, view.list, view.metric, view.trend
  partial: view.trend
```

`RECORD_LOG_WITH_TOTAL_AND_TREND` のような**合成名は作っていない**。

---

## 3. 「誰が構造を作ったか」を型で持つ（§3）

Level 0 が「deterministic な Capability Plan」を「Local AI が構造を
生成した」と誤認できる状態だった。

`GenerationStructureSource` を新設した:

```
CURATED / DETERMINISTIC_CAPABILITY_PLAN /
AI_ENTITY_SYNTHESIS / AI_GENERATED_EXTENSION / COMPOSED / UNKNOWN
```

`structure_source_is_ai()` が真になるのは **AI_* の2つだけ**である。

- `CognitiveContext` に**構造化された値として**持つ
- **Decision Trace の文字列を parse しない**（書式が変わると黙って壊れる）
- `provider_used` が LOCAL_AI/CLOUD_AI でも、構造が deterministic なら
  `GenerationSource.COMPOSITION` へ落とす

本番 HTTP 経由の実測:

```
source: TEST_DOUBLE
structure_source: DETERMINISTIC_CAPABILITY_PLAN
structure_task: cognitive_stage
```

---

## 4. CapabilityUsageEvidence（§4）

`GenerationRecord` へ、1生成物につき Capability ごとに1件:

```
capability_id / requested / used / status / source
```

実測（「部署ごとの売上を月別に集計してグラフで比べたい」）:

```
data.entity        req=True used=True implemented semantic_plan
data.number        req=True used=True implemented semantic_plan
data.text          req=True used=True implemented semantic_plan
interact.edit      req=True used=True implemented semantic_plan
view.bar_chart     req=True used=True implemented semantic_plan
view.group_compare req=True used=True implemented semantic_plan
view.list          req=True used=True implemented semantic_plan
```

**値も利用者の文も入っていない。** 型で持つ（dict の詰め合わせにしない）。

> `used=True` の意味は「その Widget が生成物に在る」であって
> 「データを入れたときに正しく見える」ではない。Round 5 で
> **空の `bar_chart` が無言の箱になっていた**のがその差である（§7）。

---

## 5. 作れないと分かっていることを伝える（§5 / TD90）

`capability_gap` を**成功レスポンスを組む唯一の場所**（`_result_dto()`）
へ載せた。新しい経路を足した人が呼び忘れても載る。

本番 HTTP の実測:

| need | 応答 |
|---|---|
| 旅行の写真を日付ごとに残してメモを付けたい | 「写真そのものは扱えません。ファイル名やメモを文字として残します。写真・日付・メモを記録するところまでなら作れます。」 |
| 植物を育てながら音を組み合わせるゲームを作りたい | 「音や画像を合成する・時間を進める・ゲームとして動かすは、いまの Forge ではまだ作れません。…植物・音を記録するところまでなら作れます。」`blocks_completion: true` |
| 英単語を出題して、正解率の推移を見たい | 「時系列のグラフはまだ描けません。日付順の一覧と合計で近似します。」 |

- wizard にしていない。**会話へそのまま流せる日本語**である
- 内部 ID を利用者向け文へ出していない
- **新しい状態 Enum を作っていない。** 既存の `release_ready` を
  false にする（`SIMULATE` / `EFFECT` が欠けたときだけ critical）

---

## 6. Semantic Layout Composition（§6 / TD91）

`LayoutEmphasis`（INPUT_FIRST / MEDIA_FIRST / SUMMARY_FIRST /
COMPARISON_FIRST / TASK_FIRST / NONE）を `CapabilityPlan` から導出し、
タブ順と強調を変える。

実描画で確認できる差:

| app | 先頭タブ | 由来 |
|---|---|---|
| finance | 家計簿記録**一覧**（残高・収入計・支出計） | SUMMARY_FIRST |
| analytics | 売上記録**一覧** | COMPARISON_FIRST |
| study | 単語**一覧**（正解率の平均） | SUMMARY_FIRST |
| photo | 写真記録**を追加** | MEDIA_FIRST |
| game | 植物**を追加** | INPUT_FIRST |

**専用 photo UI / study UI / analytics UI は1つも作っていない。**
同じ Renderer・同じ Widget 語彙で、並べ方だけが違う。

---

## 7. 操作して撮った（§7 / TD92）

`scripts/capture_quality_gate_r5.py`。14 state × 4 viewport = **56枚**、
押せなかった操作 **0件**（1件でもあれば exit 1）。

### 「押したつもり」を2回踏んだ

**1回目（座標）。** `x = width*(i+0.5)/len` で押したら **desktop だけ
4件失敗**した。本文は `Center` + `maxWidth: 720` なので、1440px では
タブ列は 360〜1080 にしか無い。index 0 は x=240（余白）へ落ちていた。
**index 1 だけが偶然 x=720＝中央で当たっていた。**
→ 座標を Dart の値から読むようにした。

**2回目（差分の穴）。** 「押す前と絵が変われば成功」には穴が2つあった。

1. `InkWell` の hover はタブが変わらなくても絵を変える
   → 撮る前にカーソルをタブ列の外へ動かす
2. もともと選ばれているタブは押しても変わらない
   → 別のタブを**経由してから戻る**（往復の両方で変化を要求）

穴1のせいで mobile の「一覧タブ」は**切り替わっていないのに成功扱い**
だった。

### 撮ったものが古かった

最初の撮影は**前日の build** に対して走っていた（fixture は当日
09:26 に再生成済み）。**古い build の絵は Evidence ではない**ので
52枚を捨て、build し直して撮り直した。

### 見つけて直した実バグ

一覧の空表示のすぐ下に、**文字が1つも無い灰色の箱**が描かれていた。

`bar_chart` は0件のとき `SizedBox.shrink()` を返すが、
`style_role: card.summary` の見た目は `applyForgeRole()` が**外側から**
被せるので、中が空でも card の padding だけが残る。

**直した**: 空のときは見出しと「グラフに出せる記録がまだありません」を
出す。再描画して再評価し、この manifest の絵は**直した後**である。
戻したら落ちるテストを置いた（配線破壊試験で確認済み）。

> **静的なテストは全部通っていた。** 撮って、開いて、見るまで
> 誰も気付かなかった。

### Golden Gate は FAIL のまま

`game-initial-mobile-390x844.png` は「植物」「音」を入れて保存する
CRUD フォームである。**ゲームではない。**
正直さの層（§5）は働いているが、作れてはいない。**結果を先に決めない。**

---

## 8. 機械非依存の方針（§8）

`docs/MACHINE-INDEPENDENT-POLICY.md` を SoT にした。

**訂正した2点:**

1. **実行機を固定しない。** 020A の「Claude の container か別実機か」は
   恒久的な実行機があるように読める。正しくは
   **「その時 Local Model を実行できるPCが、そのセッションの
   Execution Host」**である。
2. **GPU を Benchmark の絶対条件にしない。** CPU で Real Model が動いて
   実測できるなら Benchmark 自体は有効である（遅くても、出た数字は
   実測）。GPU / VRAM は**性能・遅延・載るモデルの大きさ**の Evidence
   として別に報告する。

`scripts/forge_doctor.py` も直した（読むだけ・install しない）。
このセッションでの実行結果:

```
✓ 可    GitHub 同期（push / fetch）
✗ 不可  open-weight model の取得
✗ 不可  Level 0（実 Local Model の E2E）
✗ 不可  Level 0.5（Baseline Benchmark。GPU は不要）
✗ 不可  GPU での実行（性能・遅延・載るモデルの大きさ）
```

古い Next Task（「別実機を用意する」前提のもの）は削除した。

---

## 9. Mutation（§9）

**壊す → 対応するテストが落ちる**ことを1件ずつ確認した。
今回追加分（M13 / M14）:

| # | 壊したもの | 落ちたテスト |
|---|---|---|
| M13 | Round 5 の撮影対象を全部「初期タブ」へ戻す | `test_forge_020a2_round5_capture.py::test_every_captured_app_has_a_state_behind_a_tab` |
| M14a | `forge_doctor` の Level 0.5 を再び GPU 必須にする | `test_forge_020a2_machine_policy.py::test_cpu_only_runtime_can_still_run_the_baseline_benchmark` |
| M14b | 方針文書を「常設の実機」前提へ戻す | 同 `::test_the_execution_host_is_decided_per_session` ほか計4件 |

加えて、今回の実バグ修正にも配線破壊試験を行った:
`bar_chart` を `SizedBox.shrink()` へ戻すと
`frontend/test/json_ui/widget_registry/empty_bar_chart_test.dart` が
1件 FAIL する（確認済み）。

---

## 10. 検証（§10）

**LOCAL の実測値。CI の件数と混ぜていない。**

| 対象 | 結果 |
|---|---|
| `backend` 全件 | **1845 passed / 16 skipped**（020A3 との merge 後） |
| `forge_ai` 全件 | **585 passed**（同上） |
| `flutter analyze` | **No issues found!** |
| `flutter test` | **516 passed** |
| `flutter build web`（撮影ハーネス） | 成功 |
| `ruff`（変更した全ファイル） | All checks passed |
| Playwright Round 5 | **56枚 / 失敗 0件**（exit 0） |

> repo 全体の ruff には既存の指摘が残っている（CI 対象外）。
> **「変更したファイルが clean」であって「repo 全体が clean」ではない。**

### 検証区分

| 区分 | 内容 |
|---|---|
| 実測 | 上記すべて。`capability_gap` / `CapabilityUsage` は本番経路から取得 |
| Test Double | 生成は `provider=mock`。実 API は呼んでいない |
| 未検証 | Real Local Model（**runs = 0**）、実機描画、実データ投入後の一覧・グラフ |

---

## 11. 見つけて**直していない**もの（負債として登録）

| # | 内容 |
|---|---|
| TD93 | 一覧 card とグラフ card が隙間なく接する（角が衝突して見える） |
| TD94 | 320px で「家計簿記録を…」が2つ並び、追加と編集が見分けられない |
| TD95 | 「〜ごと」「月別」「出題」が `requested` に載らず、落ちても gap に出ない |
| TD96 | 入力欄のラベルが placeholder 兼用で、入力すると項目名が消える |

**TD95 が一番重い。** 「黙って落ちる」は
`GENERATIVE-SOFTWARE-DIRECTION.md` が禁じている形そのものである。
§5 で作った告知の仕組みは正しく動くが、**Plan に載らないものは
告知もされない**。次は語彙側（Semantic Role → Capability）である。

---

## 12. 実機で Level 0 を測った（020A3、ChatGPT 側の成果）

**同じ branch で ChatGPT 側も 020A2/020A3 を実装していた。**
その中に、この container では出来ないことが1つある——
**実機で Real Local Model を動かした**。

Windows 実機（`DESKTOP-1JNGG6N`）、Ollama 0.32.15、
`qwen2.5:7b-instruct`（digest あり、Q4_K_M）。

| Evidence | 結果 |
|---|---|
| `level0-20260827-103251.json` | FAILED（Provider 120秒 timeout。修正済み） |
| `level0-20260827-103709.json` | **INVALID_PROBE** |
| `level0-20260827-104126.json` | **INVALID_PROBE** |
| `level0-20260827-104538.json` | **INVALID_PROBE** |

後半3件は production HTTP 200 / Validator PASS / Evidence uid /
`generation_source=local_ai` まで**通っている**。それでも数えない——
**構造を作ったのは決定的な fallback** だったからである。

```
why_not_counted: Software structureをLocal Modelが作っていない（curated）
real_local_model_runs: 0
```

> **これが §3 を作った理由そのものである。**
> 「Local を指定して 200 が返った」だけで数えていたら、ここで 1 が立って
> いた。実際に実機で動かして、実際に危うく数えるところだった。

**Real Local Model runs は 0 のままである。** 増やしていない。

### 実機側で直したもの（020A3）

- Windows の CP932 で起動できなかった
- script 180秒 / Provider 120秒という timeout の不一致

---

## 13. 020A3 との統合（merge の判断を残す）

2つの実装が同じ指示に別々に答えていたので、**同じものが2系統**になって
いた。**それは §1 が禁じている状態そのもの**なので、1つへ寄せた。

| 重複していたもの | 寄せ先 | 理由 |
|---|---|---|
| Capability の表（`data.*` と `record.*`） | `forge_ai/core/semantics/capabilities.py` | `label_ja` / `SafetyClass` / `limitation` を持つ側でないと §5 の日本語が作れない |
| `StructureSource` 等の型が3箇所 | `structure_provenance.py`（backend は**別名**） | 同じ値の enum が2つあると `is` が常に False（TD85） |
| `GenerationRecord` の構造欄が2組 | `structure_source` / `structure_provider` / `structure_task` | dataclass に同名欄が2つあり、後勝ちで片方が死んでいた |
| `RealLocalModelRun.structure_provenance` と `structure_source` | 欄は1つ、旧名は property | 同じ事実を2欄で持たない |
| `_capability_usage()` が2つ | 生成物の widget と突き合わせる側 | 状態だけから `used` を決めると M2b mutation を素通りする |
| `probe_was_curated` と `probe_bypassed_model_structure_generation` | 前者、後者は別名 | 同じ判定だった |

型を1つにしたので、**`structure_provider` は enum になった**
（020A3 の判断を採った）——決定的経路は `NONE` であり、空文字ではない。
「記録し忘れ」と「AI を呼んでいない」が同じ値になると区別できない。

### 採らなかったもの（理由を書く）

020A3 は「不足 Capability があれば `needs_confirmation` を返して生成を
止める」を入れていた。**採らなかった。**

1. 指示は「作れないことを**会話の中で普通に伝える**。wizard 化しない」
   である。はい／いいえを1段挟むのは wizard の作り方そのものである。
2. 判定が `unsupported`（欠けたもの全部）だった。「地図で見たい」が
   欠けただけで釣果記録まで止まる——`capability_gap` の表が
   「VIEW / INTERACT は critical ではない（見え方が落ちるだけで道具は
   使える）」と書いているのと食い違う。
3. 止めると**何も返らない**ので、作れる範囲さえ利用者へ渡らない。
   Quality Gate の視覚 Evidence も game について取れなくなる。

代わりに `_result_dto()` が `capability_gap` を必ず載せ、本質
（`SIMULATE` / `EFFECT`）が欠けていれば `release_ready` を false にする。
**「仕上がっている」とは言わない**が、**作れる範囲は渡す。**

> これは判断であって、消し忘れではない。異論があればここを見てほしい。

---

## 付録: 020A3 側の報告（原文）

# FORGE-020A2 / GENERATED-UI-QG-V2-R5 Report

- Branch: `claude/forge-master-handoff-k46jns`
- Start HEAD: `29d7c0aa3bff2231bed9e67496f8c9331a40a766`
- Implementation HEAD: `a796481724cb61abae50831ec99de30ebe86d6a2`
- Date: 2026-08-27
- Real Local Model runs: **0**
- Overall: **INCOMPLETE — Level 0は未PASS**

## Implementation / production wiring

`GenerationRecord.structure_provenance`を追加し、リクエスト中にLocal Providerが
応答した事実と、Software structureを実際に決めた主体を分離した。

```
pipeline entity_source
  → prompt_pipeline._structure_provenance
  → durable GenerationRecord
  → verify_local_model_level0.py
  → RealLocalModelRun.counts_as_real_local
```

Level 0はproduction `/generate`、AIRouter task観測、Validator、Evidence uid、
`generation_source=local_ai`に加え、`structure_provenance=local_ai`を必須とする。
deterministic Capability Plan / Curated fallbackが構造を作った場合はHTTP 200でも
`INVALID_PROBE`であり、runへ加算しない。

Level 0既定モデルは`qwen2.5:7b-instruct`。`bge-m3`はembedding専用で生成未使用。
モデルdownloadは行っていない。Windows UTF-8表示とscript/provider timeoutの
不一致も修正した。

## Tests / mutation

- focused: **105 passed**
- backend full: **1779 passed, 17 skipped**
- forge_ai full: **567 passed**
- ruff changed Python: PASS
- `git diff --check`: PASS
- mutation: deterministic Capability PlanをLOCAL_AIと同様に許可すると、専用
  偽PASS防止テストが`counts_as_real_local=True`となりFAIL。復元後green。

## Real machine Level 0

Ollama API/model availabilityを各公式実測前に確認した。Runtime 0.32.15、
model `qwen2.5:7b-instruct`、digest
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`。

- `level0-20260827-103251.json`: FAILED（Provider 120秒timeout、修正済み）
- `level0-20260827-103709.json`: INVALID_PROBE
- `level0-20260827-104126.json`: INVALID_PROBE
- `level0-20260827-104538.json`: INVALID_PROBE

後3件はproduction HTTP 200、Validator PASS、Evidence uid、
`generation_source=local_ai`まで通ったが、structureは決定的fallback由来だった。
したがって真のPASSではなく、**Real Local Model runs = 0**。

単独entity synthesisおよび一時的production診断では有効構造と
`entity_source=synthesized(generic)`を観測したが、公式Evidenceではないため
runへ加算していない。

## QG-V2-R5 visual status

この変更はEvidence/Level 0判定とCLIのみで、UI・renderer・Design Language・
generated-app appearanceを変更していない。新規visual captureは**対象外**。
既存Golden GateのFAIL状態は変更しておらず、R5 visual quality改善は
**INCOMPLETE**である。

## GitHub handoff / UNVERIFIED / next task

- Implementation commit `a796481`をpushし、local/remote一致を確認。
- GitHub Actions run `33033252955`: **success**。4 jobsすべてgreen。
- TD91: Entity synthesis不採用理由をraw応答なしの閉じたreason codeでdurable化。
- Level 0 Integrity条件を緩めず、公式Evidenceでstructure generationがLocal AI
  由来になった場合だけrunsを1へ更新する。
