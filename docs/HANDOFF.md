# Forge Handoff

- Branch: `claude/forge-master-handoff-k46jns`
- Implementation Agent: **Claude Code**
- Current phase: R1 Generated App Quality / Growing AI
- Current task: **FORGE-020A3B / CLOSEOUT-INTEGRITY-AND-CI-RECOVERY** — 完了
- 前段: FORGE-020A2 / QG-V2-R5、FORGE-020A3（どちらも統合済み）
- Golden Quality Gate: **FAIL**（理由は下記。結果を先に決めていない）
- **Real Local Model runs: 0**（実 Local Model を動かしていないので増やしていない）
- 詳細: `docs/reports/FORGE-020A3B-CLOSEOUT-report.md`
  ／ `docs/reports/FORGE-020A2-QG-V2-R5-report.md`
- 視覚 Evidence: `docs/visual-evidence/QUALITY-GATE-V2/round-5/manifest.md`

---

## CEOへの依頼

### 1. OpenAI API key の失効（**前セッションから継続**）

以前チャットへ貼られた key（`sk-proj-...`）は**どこにも保存していない**
（Source / Test / 文書 / ログのいずれにも無い）。
**まだ失効させていないなら失効させてほしい。**

### 2. 実機での Level 0 を、もう1度お願いしたい

**実機での計測はもう始まっている。** ChatGPT 側が Windows 実機
（Ollama 0.32.15 / `qwen2.5:7b-instruct`）で4回測った
（`docs/evidence/level0/`）。

**結果は Level 0 未達である。** ただし「Local Model が駄目だった」ので
はない——**測定が成立していない**（`INVALID_PROBE`）。
HTTP 200 も Validator も通ったが、**構造を作ったのが決定的な fallback**
だったので数えていない。

```
why_not_counted: Software structureをLocal Modelが作っていない（curated）
real_local_model_runs: 0
```

次に測るときは、**curated へ落ちない need** で走らせてほしい
（script が自動で選ぶようになっている）。

**GPU は要らない。** CPU で小型モデルが動けば Level 0 も Level 0.5 も
成立する（`docs/MACHINE-INDEPENDENT-POLICY.md` §6.1、020A2 §8 で訂正）。

手順（そのPCで）:

```
ollama serve
ollama pull qwen2.5:1.5b-instruct

export FORGE_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
export FORGE_LOCAL_MODEL=qwen2.5:1.5b-instruct
python scripts/verify_local_model_level0.py
```

結果は `docs/evidence/level0/<timestamp>.json` へ出る。
**PASS したときだけ** `Real Local Model runs` を増やす。

そのPCで何が通せるかは `python scripts/forge_doctor.py` が答える
（**読むだけ。install しない**）。

### 3. 同じ branch で2つのAIが同時に実装していた（**方針の確認**）

020A2/020A3 を **Claude と ChatGPT が並行して実装**しており、merge 時に
同じものが2系統になっていた（Capability の表、`StructureSource` の型、
`GenerationRecord` の欄、`_capability_usage()` など）。

**1つへ寄せた**（`CHANGELOG.md` / report §13 に対応表）。
1件だけ**採らなかった**判断があるので、そこだけ見てほしい:

> 020A3 は「不足 Capability があれば `needs_confirmation` を返して
> **生成を止める**」を入れていた。指示は「会話の中で普通に伝える。
> **wizard 化しない**」であり、判定も「欠けたもの全部」だった
> （「地図で見たい」が欠けただけで釣果記録も止まる）。
> 代わりに `capability_gap` を必ず返し、本質が欠けていれば
> `release_ready` を false にする形にした。

作業を分ける（別 branch にする / 担当領域を分ける）かどうかは、
CEO の判断をもらえると助かる。

### 4. Capability ID の綴りを揃え直すか（**判断がほしい**）

020A3B の指示書は fields を `record.*`、合成を `media.*` と書いていた。
それは **020A3 branch の綴り**であり、merge 済みの正典（GitHub 上の
現在の Source of Truth）は `data.*` / `effect.media_compose` である。

指示の**要件**——「責務ごとに namespace を分ける」「Plan が出す全 ID が
Catalog にある」——は満たしており、機械が検査している。

**綴りを `record.*` / `media.*` へ揃え直すかは CEO の判断**なので、
勝手には変えていない。やるなら機械的な rename で、invariant テストが
守る（QG 生成物の再出力も要る）。

### 5. CI runner の割当（**継続確認**）

`run 32983961000`（HEAD `87991ef`）は failure だが**コードが1行も
実行されていない**（4 jobs すべて queued / steps 0 / runner 未割当、
5秒で終了）。GitHub Actions 側の事象である。

その後の push では runner が付いており、**この blocker は再発していない**。
Actions の利用枠・runner 割当を一度確認してもらえると確実である。

---

## 020A2 で何をしたか（Reviewer 判定 NO-GO の3件を含む）

### §1 Capability Registry の SoT が2系統だった → 1つにした

正典は `forge_ai/core/semantics/capabilities.py`（31件: IMPLEMENTED 14 /
PARTIAL 3 / MISSING 14）。

`backend/app/ai/runtime/capability.py` は **Runtime Capability Adapter**
になった。持つのは `_RUNTIME_BINDINGS`（capability id → widget type）
**だけ**である。

- `supported` は `SupportLevel` から、`requires_confirmation` は
  `SafetyClass` から**導出**する（同じことを2箇所で手書きしない）
- `forge_ai` は `backend` を import しない（向きは backend → forge_ai）
- 整合は機械が検査する（binding に正典外の id があれば落ちる）

### §2 PlanShape が排他的で、要求を落としていた → 直交成分へ

「部署ごとの売上を比較して、合計と月別推移も見たい」で再現テストを
先に書いた。Shape 1値では2つが黙って落ちる。

```
CapabilityPlan = structure × views × interactions × effects
不変条件: requested にあるものは必ずどこかに現れる
```

合成名（`RECORD_LOG_WITH_TOTAL_AND_TREND` 等）は作っていない。

### §3 「誰が構造を作ったか」を型で持つ

`GenerationStructureSource`（CURATED / DETERMINISTIC_CAPABILITY_PLAN /
AI_ENTITY_SYNTHESIS / AI_GENERATED_EXTENSION / COMPOSED / UNKNOWN）。
AI 扱いになるのは AI_* の2つだけ。

**Decision Trace の文字列を parse しない**——`CognitiveContext` に
構造化された値として持つ。deterministic な Capability Plan が
「Local AI が構造を生成した」と誤認されなくなった。

### §4 CapabilityUsageEvidence

`GenerationRecord` へ、Capability ごとに
`capability_id / requested / used / status / source` を型で残す。
**値も利用者の文も入れない。**

### §5 TD90 — 作れないと分かっていることを伝える（**解消**）

`capability_gap` を `_result_dto()`（成功応答を組む唯一の場所）へ載せた。
本番 HTTP の実測:

> 「音や画像を合成する・時間を進める・ゲームとして動かすは、いまの
> Forge ではまだ作れません。…植物・音を記録するところまでなら
> 作れます。」`blocks_completion: true`

wizard にしていない。内部 ID を利用者向け文へ出していない。
**新しい状態 Enum は作らず**、既存の `release_ready` を false にする。

### §6 TD91 — Semantic Layout Composition（**解消**）

`LayoutEmphasis` を Plan から導出してタブ順と強調を変える。
finance/analytics/study は一覧が先頭、photo は入力が先頭になった。
**専用 photo UI / study UI / analytics UI は1つも作っていない。**

### §7 TD92 — 操作して撮る（**解消**）

Playwright で実際にタブを押してから撮る。
**56枚 / 押せなかった操作 0件**（1件でもあれば exit 1）。

---

## §7 で踏んだこと（同じ失敗を3度やらないため）

### 1. 古い build を撮っていた

最初の撮影は**前日の build** に対して走っていた（fixture は当日
再生成済み）。**古い build の絵は Evidence ではない。**
52枚を捨て、build し直して撮り直した。

### 2. 「押したつもり」を2回踏んだ

**座標。** `x = width*(i+0.5)/len` で押したら **desktop だけ4件失敗**。
本文は `Center` + `maxWidth: 720` なので 1440px ではタブ列は 360〜1080 に
しか無く、index 0 は余白へ落ちていた。**index 1 だけが偶然中央で
当たっていた。** → 座標を Dart の値から読む形へ。

**差分の穴。** 「押す前と絵が変われば成功」には穴が2つあった。
(a) `InkWell` の hover はタブが変わらなくても絵を変える
(b) もともと選ばれているタブは押しても変わらない。
→ 撮る前にカーソルをタブ列の外へ動かし、初期タブへ行くときは
**別のタブを経由してから戻る**（往復の両方で変化を要求）。

穴 (a) のせいで mobile の「一覧タブ」は**切り替わっていないのに成功扱い**
になっていた。

### 3. 実バグを1件見つけて直した

一覧の空表示のすぐ下に、**文字が1つも無い灰色の箱**が描かれていた。

`bar_chart` は0件のとき `SizedBox.shrink()` を返すが、
`style_role: card.summary` の見た目は `applyForgeRole()` が**外側から**
被せるので、中が空でも card の padding だけが残る。被せる側は中が空だと
知らない。

空のときは見出しと「グラフに出せる記録がまだありません」を出す形へ直し、
**再描画して再評価した**（round-5 の絵は直した後）。戻したら落ちる
テストを置き、配線破壊試験で確認した。

> **静的なテストは全部通っていた。** 撮って、開いて、見るまで
> 誰も気付かなかった。

---

## §8 機械非依存の方針（訂正2件）

`docs/MACHINE-INDEPENDENT-POLICY.md` が SoT。

1. **実行機を固定しない。** 020A の「Claude の container か別実機か」は
   恒久的な実行機があるように読める。正しくは**「その時 Local Model を
   実行できるPCが、そのセッションの Execution Host」**である。
2. **GPU を Benchmark の絶対条件にしない。** CPU で Real Model が動いて
   実測できるなら Benchmark 自体は有効である。

`scripts/forge_doctor.py` の判定も直した。このセッションでの結果:

```
✓ 可    GitHub 同期（push / fetch）
✗ 不可  open-weight model の取得
✗ 不可  Level 0（実 Local Model の E2E）
✗ 不可  Level 0.5（Baseline Benchmark。GPU は不要）
✗ 不可  GPU での実行（性能・遅延・載るモデルの大きさ）
```

---

## Golden Quality Gate は FAIL のまま

`round-5/game-initial-mobile-390x844.png` は
**「植物」「音」を入れて保存する CRUD フォーム**である。ゲームではない。

正直さの層は働いている（`blocks_completion: true`、作れない旨を明言）。
しかし**作れてはいない**。「普通のアプリとして使いたい品質」に
達していないので FAIL。**結果を先に決めていない。**

---

## 検証（LOCAL の実測。CI の件数と混ぜていない）

| 対象 | 結果 |
|---|---|
| `backend` 全件 | **1884 passed / 16 skipped**（020A3B 後） |
| `forge_ai` 全件 | **585 passed** |
| `flutter analyze` | **No issues found!** |
| `flutter test` | **516 passed** |
| `flutter build web`（撮影ハーネス） | 成功 |
| `ruff`（変更した全ファイル） | All checks passed |
| Playwright Round 5 | **56枚 / 失敗 0件** |

> repo 全体の ruff には既存の指摘が残っている（CI 対象外）。
> **「変更したファイルが clean」であって「repo 全体が clean」ではない。**

### CI（最新 HEAD）

| run | HEAD | 結果 |
|---|---|---|
| `33064545042` | `77d1a05` | **4 jobs すべて success** |

> **020A3 の3 commit（`8ca31a7` / `a6ce369` / `df42dbf`）は赤だった。**
> backend テストが Python 3.11 / 3.12 の両方で落ちていた。
> `77d1a05`（020A2/R5 と 020A3 の merge）が解消している。

### Mutation（§9）

M1–M12 は 020A2 の実装時に確認済み。今回追加分:

| # | 壊したもの | 落ちたテスト |
|---|---|---|
| M13 | Round 5 の撮影対象を全部「初期タブ」へ戻す | `test_forge_020a2_round5_capture.py` 1件 |
| M14a | `forge_doctor` の Level 0.5 を再び GPU 必須に | `test_forge_020a2_machine_policy.py` 1件 |
| M14b | 方針文書を「常設の実機」前提へ戻す | 同 4件 |
| — | `bar_chart` を `SizedBox.shrink()` へ戻す | `empty_bar_chart_test.dart` 1件 |

---

## 020A3B で直したこと（要点）

**指示書の前提を1つ訂正した。** 指示は HEAD を `a6ce369`（CI FAILURE）と
していたが、着手時点の最新は `77d1a05` で **CI は全 green** だった。
§1（CI recovery）は完了済みだったので、条件（テストを消していないか、
昔の動作へ戻していないか）だけ確認した。**§2〜§5 には本当に未着手のものが
あった。**

### §3 Level 0 が「誰が構造を作ったか」を見ていなかった（**実バグ**）

`RealLocalModelRun` に `structure_provider` も `structure_task` も
無かった。`AI_ENTITY_SYNTHESIS` は「**AI が**作った」までしか言わない
ので、**Cloud が設計した実行が Local Model の実績として Level 0 に
数えられる**状態だった。

Level 0 は Provider（`LOCAL`）と stage（`entity_synthesis`）を独立に
要求し、**その Task が実際に AIRouter を通ったこと**まで見る。
Mutation M1–M5 すべてで落ちることを確認した。

### §4 未知の Capability ID が黙って「作れません」に化けていた

綴り間違いや Catalog への足し忘れが MISSING になり、利用者へ**嘘の説明**
として出ていた。落とすようにした（`UnknownCapabilityError`）。

`effects` / `structure_capabilities` が Evidence へ**一度も届いて
いなかった**のも直した（「作ったが呼ばれない」5回目）。

### §5 PARTIAL が「成功」として学習される状態だった

`data.photo` と `partial:data.photo` が Evidence に**両方**入っていた。
素の並びを読む Dataset Builder は「写真を扱えた」を成功例として学習する
——実際には写真そのものは扱えない。素の ID は「全部出来て、実際に
使った」の意味に限った。

### §2 Quality Gate を Need の種類で分けた

`capability_gap.blocks_completion` という**述語1つ**で振り分ける。
Need 名の分岐は作らない。critical missing の Need は「文書の品質」では
なく「**完成品を偽っていないか**」で見る。

---

## 次にやること

**020B production wiring はまだ開始していない**（CEO指示）。

**020A4 へは進んでいない。**

先に片付けるべきは **TD95** である。

> 「日付ごとに」「月別に集計」「出題して」が `requested` に**載らない**。
> 載らないので、落ちても `capability_gap` に出ない。
> §5 で作った告知は正しく動くが、**Plan に載らないものは告知もされない。**

「黙って落ちる」は `GENERATIVE-SOFTWARE-DIRECTION.md` が禁じている形
そのものである。直す場所は語彙側（Semantic Role → Capability）。

その他の新規負債は `TECH_DEBT.md`（TD93 / TD94 / TD96）。

---

## UNVERIFIED（正直に）

| 項目 | 状態 |
|---|---|
| Real Local Model の E2E（Level 0） | **未達**。実機で4回測ったが `INVALID_PROBE`（構造が決定的 fallback 由来）。runs = 0 |
| Baseline Benchmark（Level 0.5） | **UNVERIFIED**。Runtime が無い |
| 実機（iOS / Android）での描画 | 未検証。web のみ |
| 実データを入れた後の一覧・グラフ | 未検証。空状態のみ撮影 |
| 生成 Provider | **Test Double**（`provider=mock`）。実 API は呼んでいない |
