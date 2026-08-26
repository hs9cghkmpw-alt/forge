# FORGE-020A1 / GENERATED-UI-QG-V2-R4 — report

- Task: Evidence Integrity + Generative Capability Planning（CEO指示、2026-08-26）
- Branch: `claude/forge-master-handoff-k46jns`
- Implementation Agent: Claude Code
- **Real Local Model runs: 0**（変えていない。このPCでは測れない）

---

## 0. 結論を先に

| | 結果 |
|---|---|
| CI（HEAD 87991ef の run 32983961000） | **infrastructure failure**（コードの失敗ではない） |
| Level 0 script の Evidence Integrity（A/B/C/D） | ✅ 4件とも修正 |
| TD89（Domain 判定が外れる） | ✅ **解消**（実描画で確認） |
| TD87（8アプリが3種類の画面） | ✅ **解消**（32枚に重複が1枚も無い） |
| **Golden Quality Gate（Round 4）** | ❌ **FAIL**（理由が変わった。下記 §5） |

---

## 1. CI failure の原因（最優先1）

`run 32983961000` は `conclusion=failure` だが、**コードは1行も実行されていない**。

```
created_at : 15:03:53Z
updated_at : 15:03:58Z   ← 5秒
jobs       : 4件すべて status=queued / steps 0 / runner 未割当
```

同一に近いコードの1つ前の commit（`89fbc72`）は **success** である。
テスト内容ではなく **runner が1台も割り当たらないまま run が打ち切られた**
——GitHub Actions 側の事象である。

`rerun_workflow_run` で再実行を要求した（`run_attempt` が更新され
`run_started_at=20:31:00Z`）。ただし **本 report を書いている時点でも
jobs は 0 件のまま**であり、**green evidence はまだ取れていない。**

> **最新 HEAD を CI PASS とは書かない。** green になるまで、この行は
> 「未取得」のままにする。

---

## 2. Level 0 script の修正（最優先2）

### A. probe が Curated へ落ちていた

既定の probe「毎日の支出を記録して合計を見たい」を本番へ通して実測:

```
domain_resolution = curated
reason = 'household_budget'の概念語(transaction)が発話に現れており、手作り定義が適合する
```

Curated 経路は**AI を1回も呼ばずに**文書を作る。Runtime が動いていようが
いまいが HTTP 200 が返り、Validator も通る。
**あの probe では Local Model が仕事をしたかを一切測れない。**

直したこと:

- `LEVEL0_PROBE = "実験の条件と結果を残して、条件ごとに成功率を比べたい"`
  （実測で `domain_resolution=generated` / `domain=generic`）
- `CURATED_TRAP_PROBE` として旧 probe を**理由ごと残す**——消すと同じ罠を踏む
- **実行の前と後**の両方で `domain_resolution` を確認する。前は
  `provider=mock` で確かめる（Local Model の枠を使わない）
- Curated へ落ちた場合は `Level0Outcome.INVALID_PROBE`。
  **Local Model の FAIL ではなく、測定の不成立**として扱う
- 終了コードも分ける（PASS=0 / FAILED=1 / **INVALID_PROBE=2**）

`backend/tests/test_forge_020a_local_model_path.py` が、
**本番の `/generate` へ実際に通して** probe の解決先を検査する。
定数を目で見ても Curated かどうかは分からない——実際に落ちていた。

### B. Task を手で書いていた

script は `RealLocalModelRun.task` に
`ForgeTask.FORGE_LANGUAGE_UPDATE` を**定数として**書いていた。
本番の `/generate` が通すのは `ForgeTask.COGNITIVE_STAGE` である
（`prompt_pipeline.py` の `bind(ForgeTask.COGNITIVE_STAGE, ...)`）。

Task ごとに Routing も評価も分ける設計（011 §3）なので、
**別の Task の成績として集計され、存在しない実績が生まれる。**

直したこと:

- `observed_tasks` を追加し、`ExperienceRecord.task` から**観測**する
  （AIRouter 自身が残す事実。script の主張ではない）
- `task` が `observed_tasks` に無ければ**数えない**
- 観測が空でも数えない（「AIRouter を通った Task を観測できていない」）

### C. Level 0 の範囲を限定し、Level 0.5 を分けた

以前の docstring は `BenchmarkRun` と `LocalPromotionGate` まで Level 0 の
完成条件に並べていた。**配線されていないし、1件の成功で語れるものでもない。**

| | 何を証明するか | 必要なもの |
|---|---|---|
| **Level 0** | 経路が通る（E2E Runtime 証明） | 有効な probe 1件 |
| **Level 0.5** | どれくらい使えるか（Baseline） | 重みの同一性 + 複数件 |

Level 0 の完成条件:

```
Runtime → LocalModelProvider → Provider Registry → AIRouter
  → production /generate → Validator → GenerationRecord(source=local_ai)
```

`RealLocalModelRunLog.baseline_ready_runs()` が Level 0.5 の入力である。
**1件成功しただけで PROMOTED にしない。** evidence 不足で
`NOT PROMOTED` になるのは正常な結果である。

### D. `model_id` と `model_digest` を分けた

以前は OpenAI 互換 `/v1/models` の `id`（ただの名前）を、digest が
取れなかったときの代わりに `model_digest` へ入れていた。
**名前は重みの識別子ではない。** 同じ名前で中身の違う重みを配ることは
誰にでもできる。

- `model_id` — Runtime が名乗る名前。ほぼ必ず取れる（**数えるのに必要**）
- `model_digest` — Runtime が返した重みのハッシュ。取れなければ**空のまま**
- `WeightIdentity.VERIFIED_DIGEST` / `UNVERIFIED` を新設

**ここで1つ緩めた。隠さずに書く。**
以前 `model_digest` は「数える条件」だった。1つの欄に「重みの同一性」と
「fixture 除け」を兼務させていたので、どちらも半端だった:

- digest を返さない**本物**の Runtime（llama-server 等）が永久に到達不能
- digest を返す**偽サーバ**は digest があるので通る

fixture 除けは `runtime_backend` / `generation_source` / `deployment` の
仕事である。digest は Level 0 の条件から外し、**Level 0.5 が要求する**
（`ready_for_baseline`）。緩めた分の代わりに、以前は見ていなかった
`domain_resolution` と `observed_tasks` の2検査を足した。

---

## 3. TD87 / TD89 — 生成経路そのものを変えた

### 3.1 直す前に再現した

`backend/tests/test_forge_qg_v2_r4_capability_planning.py` を**先に**書き、
7件すべてが FAIL することを確認してから着手した。

再現した事実:

| | 実測（修正前） |
|---|---|
| 「子どもが朝の支度を…」 | `child_growth` →「こどもの成長」＋ 体重測定・身長測定 |
| 「旅行の写真を…」 | `travel` →「旅行」＋ 充電器・着替え・歯ブラシ |
| analytics / game / study | **PNG が全 viewport でバイト単位一致** |

途中で**自分のテストが1件、何も検査せずに通っていた**ことにも気付いた。
`entity_source` の trace を見ていたが、その Need は `ir is None` の経路へ
落ちるので**その行が出ない**。置物だったので、必ず出る
`domain_classification` を見るように書き直した。

### 3.2 圧縮されていた経路

```
Need → keyword → Domain → Template/Compiler → checklist
```

**1つの単語がアプリ全体を決めていた。** 「子ども」が出ただけで記録対象が
体重・身長になる。

### 3.3 入れた経路

```
Need
  → Semantic Role Extraction   forge_ai/core/semantics/roles.py
  → Capability Decomposition   forge_ai/core/semantics/capability_plan.py
  → Capability Plan
  → IR Generation              forge_ai/core/ir/capability_ir.py
  → Forge Language             （既存の build_from_spec に合流）
  → Validator
  → Renderer
```

**キーワード表は無くしていない。変えたのは表の権限である。**
以前は語 → Domain であり Domain がアプリ全体を決めていた。今は
語 → **1つの役**であり、構造は役の**組み合わせ**から決まる。

役（8つ）: `actor` / `subject` / `managed_object` / `recorded_data` /
`activity` / `context` / `desired_view` / `effect`

**規則は1つ。**

> `ACTOR` と `CONTEXT` は、作るものの構造を決めてはならない。

`SemanticRoleExtraction.structural_values()` がその境界であり、
`ACTOR` / `CONTEXT` は入らない。

### 3.4 Capability Registry は語彙であって生成結果ではない

`CAPABILITY_REGISTRY` は id → (実装状態, 説明) の表である。
**Need を入れると画面が出てくる装置ではない。** 行を足しても
「作れるアプリの種類」は増えない。増えるのは
**Forge が正直に名指しできるものの種類**である。

`IMPLEMENTED` / `PARTIAL` / `MISSING` の3値を持ち、Plan は
`unsupported` と `partial` を**名指しで**持つ。
「ゲームループは無い」「写真そのものは扱えない」「推移は時系列グラフ
ではない」と書いてある。**無いものを checklist で代用して黙らない。**

### 3.5 専用 Template を作っていない

`kids_template` / `photo_template` / `analytics_template` は1つも無い。
`PlanShape` は5値（checklist / record_log / +total / +group_compare /
+trend）で、`TestNoPerNeedTemplates` が

- Shape の総数が6以下であること
- Shape 名に need 由来の語（kids / photo / analytics / travel / child）が
  含まれないこと

を固定する。

### 3.6 実測（修正後）

| Need | Shape | Entity | Fields |
|---|---|---|---|
| 子どもが朝の支度を… | checklist | 支度 | （記録しない） |
| 今日やる作業を… | checklist | やること | （記録しない） |
| 旅行の写真を… | record_log | 写真記録 | 写真 / 日付 / メモ |
| 釣った場所を… | record_log | 魚 | 魚 / 場所 / 種類 |
| 植物を育てながら… | record_log | 植物 | 植物 / 音 |
| 毎日の収入と支出を… | record_log_with_total | 家計簿記録 | （Curated 維持） |
| 部署ごとの売上を… | record_log_with_group_compare | 売上記録 | 部署 / 金額 |
| 英単語を出題して… | record_log_with_trend | 単語 | 単語 / 正解率 |

**体重・身長は出ない。持ち物リストも出ない。**

### 3.7 途中で3つ、実描画を見て直した

**(a) `group_by` だけで CONTEXT を Field へ昇格していた。**
「日付ごとに残して」の「ごと」で `group_by` が立ち、写真1枚ごとに
**「旅行」欄**が出ていた。比較（compare / aggregate）を明示的に
求められたときだけ軸として記録する、に直した。

**(b) 写真アプリもデータ分析アプリも名前が「記録」だった。**
記録している値そのものから名乗るようにした（写真記録 / 売上記録）。

**(c) 「英単語を出題して正解率の推移を見たい」に単語欄が無かった。**
正解率しか入れられず、**どの単語の正解率か記録できない**画面だった。
`MANAGED_OBJECT` は数えられる対象であり、数えられるものには1件ずつの
名前が要る——役の性質から出る一般規則として直した（植物・魚も同様）。

### 3.8 既存の Golden が2件落ちて、設計が1つ良くなった

```
「旅行の計画を立てたい」        → travel を外すと generic
「スーパーで買う物を管理したい」 → store を外すと generic
```

「旅行の写真を日付ごとに残して」の旅行が**場面**だと言えるのは、
写真・日付・メモという記録対象が別にあるからである。
**記録対象も行いも見せ方も1つも語られていない文では、その語こそが主題**
である。`structural_values()` が空なら何も block しない、という規則を
足した。役を消したのではなく、**役が主題へ格上げされる条件**を書いた。

### 3.9 副作用を1つ直した

`Intent.actors` へ actor を移した結果、
`requirement_extractor` の「actor が居れば共有・権限管理が必須」規則が
発火し、「子どもが朝の支度を…」が**確認要求へ抜けた**（Design Critic が
永久に満たせない）。

**Actor が居ることと、複数人で共有することは別である。**
「子どもが使う」は1人で使う道具である。`_MULTI_USER_ACTORS`
（家族・チーム・同僚・参加者・回答者）を分け、共有 action か
複数人 actor のときだけ要求するようにした。
`家族で共有できる買い物リスト` の Golden は変わらず通っている。

---

## 4. 配線破壊試験（14件、すべて対応テストが落ちた）

| | 壊したもの | 結果 |
|---|---|---|
| M1 | legacy compiler の名付け配線 | backend 5件 FAIL |
| M2 | IR compiler の名付け配線 | backend 4 + forge_ai 1 FAIL |
| M3 | `is_name_like()` を常に True | backend 3 + forge_ai 7 FAIL |
| M4 | 内部識別子ガード | forge_ai 4 FAIL（うち1件は本番 pipeline の E2E） |
| M5 | `generic` Domain も名前に使う | backend 1 + forge_ai 1 FAIL |
| M6 | GENERIC の代わりに要求文を返す | backend 4 + forge_ai 2 FAIL |
| M7 | ACTOR/CONTEXT を構造役へ入れる | forge_ai 4 FAIL |
| M8 | 役 gate を無効化 | backend 3 FAIL |
| M9 | Capability Plan → IR の配線を外す | backend 4 FAIL |
| M10 | `group_by` だけで CONTEXT を昇格 | forge_ai 3 FAIL |
| M11 | ACTOR/CONTEXT から Entity を作る | **最初 SURVIVED** → 下記 |
| M12 | 分からないとき checklist へ倒す | backend 1 + forge_ai 1 FAIL |
| M13 | actor が居れば共有必須へ戻す | backend 6 FAIL |
| M14 | `intent.actors` を meaning へ渡さない | backend 1 FAIL |

### M11 が生き残った（置物を1件見つけた）

`_subject_of()` は構造役だけを回っていたが、**それを守っていたのは
表の中身**（`_SUBJECT_LABELS` に `child` / `travel` が無いこと）であって、
コードではなかった。表に1行足せば Entity が「旅行」になる。

直したこと:

1. コード側でも ACTOR/CONTEXT の値を明示的に除外する
2. `_SUBJECT_LABELS` と役 lexicon の重なりが空であることを**静的検査**する
3. 表を壊してもコード側が止めることをテストする

再試験で M11 は落ちるようになった。

### 3種類を分けて数える

- **振る舞いの guard**: M1〜M14 の大半（本番 HTTP / 本番 pipeline を通す）
- **静的プロトコル検査**: `_SUBJECT_LABELS` × 役 lexicon の重なり、
  `PlanShape` の名前と個数、`forge_doctor.py` の source 検査
- **実 source の mutation**: 上表14件（すべて実ファイルを書き換えて実行）

---

## 5. Quality Gate v2 Round 4

`docs/visual-evidence/QUALITY-GATE-V2/round-4/`（**既存の `after/` は
上書きしていない**）。

```
production /generate → generated Forge Document → real Flutter Renderer
  → 4 viewport → screenshot → 画像を開く → 目視
```

### 系譜

| | 置き場 | Golden Gate |
|---|---|---|
| 第1回 | `before/` | FAIL |
| 第2回 | `after/` | FAIL |
| 第3回 | `after/`（上書き） | FAIL |
| **第4回** | **`round-4/`** | **FAIL** |

> 第3回までが `after/` を共用しているのは記録上の弱点である。
> Round 4 から versioned path にした。

### TD87 は解消した

**32枚に重複が1枚も無い**（`md5sum | uniq -d` が 0件）。
第3回では analytics / game / study が全 viewport でバイト単位一致していた。

widget 型数: 21 / 7 / 7 / 17 / 20 / 16 / 19 / 19
（第3回: 21 / 7 / 7 / 7 / 20 / 7 / 7 / 7）

### TD89 も解消した（画像で確認）

- `kids-mobile`: 「支度」＋空状態。**体重・身長は無い**
- `photo-mobile`: 「写真記録」＋ 写真 / 日付 / メモ。**持ち物リストは無い**

### それでも Golden Gate は **FAIL**

**理由が変わった。** 「同じ画面しか出てこない」ではなくなった。

1. **ゲームがゲームではない**（最大の問題）。
   「植物を育てながら音を組み合わせるゲーム」は
   **植物と音を記録する CRUD** になっている。
   Plan は `simulate.loop` と `media.compose` を `MISSING` と正しく
   名指ししているのに、**その事実が利用者に一切見えない**。
   Forge は知っているのに黙っている。
2. **record_log 系4本の第1画面が似ている。** 3タブ CRUD + フォームで、
   違うのは Field と色だけ。Shape は違うが**入口の見た目が同じ**。
3. **集計・推移の画面を撮れていない。** `bar_chart` と
   `metric_view(sum)` は文書に**実在する**（analytics.json で確認）が、
   一覧タブにあるので静止画では写らない。
   **「撮れていない」と「無い」は違う。** 前者である。

「このまま普通のアプリとして使いたいと思えるか」——
支度チェック・やることリストは**思える**。単語・写真記録は**惜しい**。
ゲームは**思えない**。よって **FAIL**。

### この評価の限界（据え置き）

- 字形は本番と違う（`fonts.gstatic.com` 拒否、撮影時のみ IPAGothic）
- contrast / accessibility は数値で測っていない（UNVERIFIED）
- **操作していない。第1タブしか写っていない**（上の 3.）
- 生成は `provider=mock`（**Real Local Model runs = 0**）

---

## 6. Machine-Independent Policy

`docs/MACHINE-INDEPENDENT-POLICY.md` を記録した。

- 常設の実行PCを仮定しない
- 共有状態は **GitHub だけ**（チャットは存在しないのと同じ）
- マシン固有の path / config を GitHub へ固定しない
- 秘密は**名前だけ**（`CLAUDE.md` §4）
- 実行できない項目は **UNVERIFIED**。`FAILED` とも `INVALID_PROBE` とも別

`scripts/forge_doctor.py` が、そのPCで何が検証できるかを**読むだけで**
調べる。インストールも設定変更もしない。

このPCでの実測:

```
✓ backend / forge_ai のテスト  ✓ Renderer のテスト
✓ Quality Gate v2（実描画）    ✓ GitHub 同期
✗ open-weight model の取得     ✗ Level 0     ✗ Level 0.5
```

`backend/tests/test_forge_doctor.py` が、
**秘密が出力へ1文字も漏れないこと**（値・長さ・先頭数文字）と、
**環境を変えないこと**、**source に install 系の呼び出しが無いこと**を
固定する。

---

## 7. 検証

```
backend  : 1768 passed, 16 skipped   (+24)
forge_ai :  567 passed               (+30)
flutter  : analyze No issues found / 514 passed
ruff     : 新規・変更ファイルは clean
CI       : **未取得**（§1、runner 未割当）
```

## 8. Real Local Model runs

**0 のまま。** このPCでは Runtime も GPU も無く、配布元へも到達できない。
勝手に増やしていない。
