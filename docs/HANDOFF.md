# Forge Handoff

## Current task: FORGE-020A3 / CAPABILITY-COMPOSITION-AND-TYPED-PROVENANCE

- Branch: `claude/forge-master-handoff-k46jns`; start HEAD: `01c45421749905bb553c84dabed56c757173e5fd`.
- Structure truth is typed on `CognitiveContext`; source/provider/task are orthogonal and `decision_trace` is diagnostic only.
- Canonical semantic catalog: `forge_ai/core/semantics/capabilities.py`; backend is the runtime adapter/binding validator.
- `StructuralMode` is unknown/checklist/record_entity. Views compose independently; list + total + group comparison + trend are retained.
- Capability usage, synthesis rejection and critical missing outcomes are typed and privacy-safe.
- Next task: independent FORGE-020A3 review and dependency-complete verification.
- Evidence: `docs/reports/FORGE-020A3-report.md`.
- Implementation commit `8ca31a7e02db767bf64c51ace3156c0ab9181e93` pushed; fetch and local/remote equality passed. GitHub returned no workflow run/status for the SHA, therefore CI is UNVERIFIED.

## 2026-08-27 FORGE-020A2 / GENERATED-UI-QG-V2-R5 update

- Start HEAD: `29d7c0aa3bff2231bed9e67496f8c9331a40a766`
- Implementation HEAD: `a796481724cb61abae50831ec99de30ebe86d6a2`
- Local AI Structure Provenanceをproduction `GenerationRecord`へ配線。
- Level 0は`structure_provenance=local_ai`を必須化。Capability Planだけが
  構造を作った場合は`INVALID_PROBE`であり、偽PASSしない。
- Ollama 0.32.15 / `qwen2.5:7b-instruct` / digest
  `845dbda0ea48...0b697e`を確認。`bge-m3`は生成に使用していない。
- 実測: FAILED 1回（Provider timeout不一致、修正済み）、INVALID_PROBE 2回。
  HTTP 200・Validator PASS・`generation_source=local_ai`でも、構造がfallback
  由来だったため拒否。**Real Local Model runs: 0**。
- Tests: backend `1779 passed, 17 skipped`; forge_ai `567 passed`;
  focused `105 passed`; ruff green。
  mutationは偽PASS guardを緩めると対象1件FAIL、復元後green。
- Evidence: `docs/evidence/level0/level0-20260827-103251.json`,
  `level0-20260827-103709.json`, `level0-20260827-104126.json`,
  `level0-20260827-104538.json`。PASS Evidenceはまだ無い。
- GitHub Actions: run `33033252955` **success**。frontend Flutter、backend
  smoke、backend+forge_ai Python 3.11/3.12の4 jobsすべてgreen。
- 次TaskはTD91（Entity synthesis応答の採否をprivacy-safeなreason codeで
  durable観測し、実モデルfallbackを改善）。
- Task report: `docs/reports/FORGE-020A2-QG-V2-R5-report.md`。
  UI変更なし。R5 visual quality改善は**INCOMPLETE**、新規captureは対象外。

---

- Branch: `claude/forge-master-handoff-k46jns`
- Start HEAD: `63ad43403606c9731f76c98248a9b0e9149e94bf`
- Implementation Agent: **Claude Code**
- Current phase: R1 Generated App Quality / Growing AI
- Historical task: **FORGE-020A1 / QG-V2-R4**（Evidence Integrity +
  Generative Capability Planning）。**TD87・TD89 は解消**、
  Golden Gate は **FAIL**（理由が変わった）
- **Real Local Model runs: 0**（2026-08-27にこのPCで実測したが、厳密判定は未PASS）

---

## CEOへの依頼

### 1. CI が runner を掴めない run がある（**要確認**）

`run 32983961000`（HEAD `87991ef`）は **conclusion=failure** だが、
**コードは1行も実行されていない**。

```
created 15:03:53Z → updated 15:03:58Z   （5秒）
4 jobs すべて status=queued / steps 0 / runner 未割当
```

1つ前の commit（`89fbc72`）はほぼ同じコードで **success**。
GitHub Actions 側の事象である。再実行を要求したが jobs 0件のままだった。

**次の push（`47c95e5`）では runner が付き、そして本当に落ちた**
（run 33015298405）。原因は**私が書いたテスト**である——
「秘密の長さを出さない」検査を数字の部分文字列探索で書いたため、
長さ 27 が runner のホスト名 `runnervm76f27` に一致した。
誤検知の余地が無い形（長さの違う2つの秘密で `env:` 行が一致すること）へ
直して push した（`f6a3f95`）。

> **2つの failure は別物である。** `32983961000` は runner 未割当
> （infrastructure、jobs 0件 / steps 0）、`33015298405` はコードの誤り
> （4 jobs すべて runner 割当・steps 実行）。混ぜない。
>
> **runner が割り当たらない件は残っている。** Actions の利用枠・
> runner 割当を確認してほしい。

### CI は green になった（`cf1f8e23`、run `33015811555`）

| job | 結果 |
|---|---|
| backend smoke（起動 + CORS） | ✅ success |
| frontend (Flutter)（analyze / test / build web） | ✅ success |
| backend + forge_ai (Python 3.11) | ✅ success |
| backend + forge_ai (Python 3.12) | ✅ success |

4 jobs すべて runner が割り当たり、steps も実行された上での success で
ある。**「runner が付かなかった run」と混同しないこと。**

### CI green の確定記録

| run | HEAD | 結果 |
|---|---|---|
| `33015811555` | `cf1f8e23` | ✅ success（4 jobs） |
| `33015909…`   | `917a495c` | ✅ success（4 jobs） |
| **`33016468327`** | **`a1c49ad4`** | ✅ **success（4 jobs、steps 9〜12）** |

> **この行自体を書き換える commit の CI は、その次の run になる。**
> 文書に「最新 HEAD は green」と書き続けると、書いた瞬間に「最新」が
> ずれる——追いかけても終わらない。
>
> **ここに残すのは「どの SHA が green だったか」である。**
> 以降の doc-only commit の CI は、Reviewer が
> `gh run list --branch claude/forge-master-handoff-k46jns` で確認できる。

> 残っている問題: `32983961000` は**いまだに `queued` のまま**である。
> Actions の利用枠・runner 割当は引き続き確認してほしい。


### 2. 前セッションから残っている件

以前貼られた OpenAI API key（`sk-proj-...`）は**どこにも保存していない**が、
**まだ失効させていないなら失効させてほしい。**

---

## 環境判断は決まった（CEO決定、2026-08-26）

**この container の network policy は広げない。**
Level 0 の実測は、インターネットへ通常接続できる**別の実機**
（Local Model Execution Host）で行う。

理由（CEO）:

- 現 container では `huggingface.co` / `ollama.com` / `github.com` が 403
- Ollama / llama.cpp / torch が無く、GPU も無い
- 配布元の追加CDNまで allowlist を広げ続けたくない
- **Forge が将来実際に動くローカルPCで測る方が deployment evidence として
  価値が高い**

### 役割分担

| | やること |
|---|---|
| **Claude Code 環境（ここ）** | 実装 / Tests / Benchmark contract / Episode / Dataset・Training foundation / GitHub handoff |
| **別実機** | Ollama または llama.cpp / Real Open-weight Model / Forge backend / LocalModelProvider / **実推論・実測** |

### 最初の Level 0 は小型 Q4 で構わない

目的は**能力評価ではなく実 E2E 証明**である。

```
Runtime → LocalModelProvider → AIRouter → Forge pipeline
  → Validator → Evidence
```

成功後に、より強いモデルで Baseline Benchmark へ進む。

### 実機での手順

```
ollama serve
ollama pull qwen2.5:1.5b-instruct

export FORGE_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
export FORGE_LOCAL_MODEL=qwen2.5:1.5b-instruct
python scripts/verify_local_model_level0.py
```

結果は `docs/evidence/level0/<timestamp>.json` へ出る。
**PASS したときだけ** `Real Local Model runs` を増やし、
Vision の Level 0 を UNVERIFIED から動かす。

> **この container では Level 0 を UNVERIFIED のまま維持する**（CEO指示）。
> 実際、ここで走らせると `FAILED` になる。それが正しい状態である。

## 何をしたか

### 019C — Revision を本当に閉じた

独立レビューの4点は**すべて現在のコードで再現できた**。先に再現テストを
書いて FAIL させてから直した。

| 指摘 | 直した形 |
|---|---|
| A. advance 失敗で CORRECTED だけ残る | **順序を変えた。** CAS で版を進めてから追記する。落ちうる段が追記より前に来たので、巻き戻す必要そのものが消えた |
| B. 投影失敗で確定済み Revision が API 失敗 | **投影を分離。** `LearningProjectionOutbox` へ pending として残る。API は成功のまま |
| C. 「単一プロセスだから割り込まない」は成り立たない | **前提を捨てた。** per-artifact lock + compare-and-swap + replay 予約 |
| D. enum の宣言と本番到達可能な操作が不一致 | **3段に分けた。** production_supported は **1件だけ** |

Rejected な Revision は **RevisionRecord 0 / FeedbackEvent 0 /
LearningEvent 0 / 版 0 / replay 0**。

### 020 — 実 Local Model が要らない部分を作った

- **Agent**: Tool Broker / Permission Broker（4段）/ Sandbox /
  Repair Loop（予算付き）。**Model へ任意 shell 文字列を渡す口は無い**
- **Web**: search / fetch / browser。本文は `UntrustedContent` に包まれ、
  **解かないと取り出せない**（Web を命令として扱わない）
- **Learning**: GenerationEpisode / Teacher 比較 / Training Gym /
  Novel Benchmark / Dataset Builder / Knowledge 昇格 Gate /
  Adapter / Self-Extension

### 方向の文書を2つ新設した

| | 何を守るか |
|---|---|
| `docs/GENERATIVE-SOFTWARE-DIRECTION.md` | **何を作る機械なのか。** 有限Widget Builderにしない |
| `docs/LEARNABLE-LOCAL-AI-VISION.md` | **作る側のAIが何になるべきか**（CEO指示を文書化） |

どちらも実装の都合で目標を縮小しないための下限である。
`PRODUCT-DIRECTION.md` は**変更していない**。

### Local AI の到達段階（Vision §39 の Level 0–10）

> **現在 Level 0（Local Model が動く）に到達していない。**

`Real Local Model runs = 0`。Level 1 以降は Level 0 を前提とするので、
**どれも到達していない。**

契約と検査は Level 2〜6 のぶんまで先に作ってあるが、
**それは「到達した」ではない。** Level 0 が解けた時点で接続できる状態に
してある、という意味である。

次に埋めるべき穴（優先順）:

1. **Level 0** — 実 Local Model（下の「CEOへの依頼」）
2. **Capability Registry の作り直し** — Registry は**在る**
   （`capability.py`、本番配線済み）。無いのは**生成的 primitive を
   表現できる形**である。いまは Widget Registry と 1:1 の人手維持なので、
   ここへ能力を足すことは Widget を足すことと同じになる（§20 が禁じた方向）
3. **能力単位の Dataset** — 完成物単位しか作れていない
4. **学習イベントの網羅** — 列挙のうち実際に出しているのは一部
5. **Gym / Novel Benchmark を実際に走らせる** — どちらも run 0件

---

## FORGE-020A — Level 0 の準備で**実バグを3つ**見つけた

実モデルは動かせないが、**動かす前に塞いでおくべき穴**が出た。
どれも「実機で測った瞬間に嘘の結果を出す」種類である。

### 1. Local Model への本番経路が1つも無かった

`local`（`LocalModelProvider`。Registry上 `IMPLEMENTED` / `LOCAL` /
構造化出力対応、`ProviderRouter` に実装も結び付いている）は、
**`/generate` `/converse` `/update` のどれからも選べなかった。**

代わりに `/generate` が受理していた `oss` は `NotImplementedError` を
投げるスタブで、Registry 自身が「`local` が実質的な後継」と書いている。

> **動く方を隠して、動かない方を公開していた。**

「作ったが本番から呼ばれない」の**7例目**である
（TD59 / 007 §10 / 010 Phase B / TD64 / TD69 / 016A / これ）。

3つとも開けた。**この穴が残ったままなら、実機でも測れなかった。**

### 2. AIを1回も呼ばずに「local が答えた」と報告していた

Runtime を起動していない状態で `provider="local"` を指定すると、
**HTTP 200 が返る**（実測 92ms、Validator も通る）。

作ったのは Curated Domain Library であり、**LLM は1回も呼ばれていない**
（`GenerationSource.CURATED`）。それでも `diagnostics.provider_used` は
`"local"` と報告していた。

原因は `_provider_used()` の `or provider`——**要求した名前を、答えた
名前として返していた**。関数自身の docstring が「呼んでいないなら
呼んでいないと言う」と書いているのに、実装がそうなっていなかった。

019B §4 で `revision_provider` について直したものと**同じ嘘**である。
`or provider` を外した。

### 3. `Deployment` enum が2つある

`provider_registry.Deployment` と `learning_events.Deployment` は別物で、
`is` 比較は必ず `False` になる。テストを書くとき取り違えて、
**条件が常に空集合になった**（緑のまま何も守らない状態）。
気付いて直したが、**踏みやすい**ので記録しておく。

## Level 0 を測るための道具

- `backend/app/ai/gateway/local_model_evidence.py`
  — **何を「実モデルで動いた」と数えるか**の契約
- `scripts/verify_local_model_level0.py`
  — 実機で1コマンド。証拠 JSON を出す

数えるには**全部**満たす必要がある。

| 条件 | 何を防ぐか |
|---|---|
| Provider が Test Double でない | Mock を数える |
| Runtime を特定できている | 「何が動いたか言えない」実行 |
| 重みの識別子がある | fixture を数える |
| **Evidence uid がある** | 横から Provider を叩いた実行 |
| **`GenerationSource.LOCAL_AI`** | **200 OK だが Curated が作った**（上記2） |
| Validator を通っている | 壊れた出力 |
| `Verification.REAL` | 未実測 |

> 偽サーバを立てて騙すことまでは防げない。**防げないと書いてある。**
> `runtime_backend` / `model_digest` / `host_id` を記録に残すので、
> 偽るなら記録に嘘を書くしかない形にしてある。

## Production wiring

```
Flutter Host / 会話
  → artifact capability（handle）
  → version token / document binding
  → replay 予約（同じ論理要求を2本走らせない）      019C §8
  → per-artifact lock（同じ生成物を直列化）          019C §7
    → TargetResolver / 全体再生成fallback
    → Validator + Semantic Design Critic
    → 本番で使ってよい操作かの検査                    019C §9
    → [ prepare → stage → commit(CAS→追記) ]         019C §4
  ← lock 解放
  → project → Learning Outbox                        019C §6
  → GenerationEpisode                                020 §18 ★今回配線
  → 新しい artifact version → Flutter render
```

| | 状態 |
|---|---|
| Revision 系 | ✅ **本番配線済み** |
| Benchmark → LocalPromotionGate → routing | ✅ 配線済み・**昇格0件**（実測が無い） |
| Agent / Web / Teacher / Gym / Novel / Dataset / Adapter | ⬜ **契約のみ。本番配線なし** |

未配線であることも**テストで固定した**——配線したのに文書を直さないと
`test_forge_020_production_wiring.py` が落ちる。

---

## Tests / Evidence

**LOCAL と CI を混ぜない。**

| | LOCAL（今回の実測） |
|---|---|
| backend | **1,708 passed / 16 skipped** |
| forge_ai | **521 passed** |
| Flutter test | **514 passed** |
| `flutter analyze --fatal-infos --fatal-warnings` | **No issues found** |
| `flutter build web --debug` | 成功 |
| backend smoke（起動 / health / CORS / generate） | 成功 |
| ruff（変更ファイル） | All checks passed |

**CI の実測**（run `32910317758` / `b89d090`、**4 job すべて success**）:

| | CI |
|---|---|
| backend Python 3.11 | **1,705 passed / 17 skipped** |
| backend Python 3.12 | **1,705 passed / 17 skipped** |
| forge_ai | **521 passed** |
| Flutter | **514 tests passed** / analyze 通過 / build web ✓ |

> LOCAL は `1,706 / 16`。`FORGE_DEFAULT_PROVIDER=mock` の有無で skip が
> 1件変わる（019B でも同じずれを記録済み）。**混ぜない。**
>
> Flutter SDK は **LOCAL 3.44.9 / CI 3.47.1**。Visual Evidence は
> 3.44.9 で撮っている。

| guard の種類 | 数 |
|---|---|
| behavior guards | **180** |
| static protocol checks | **8** |
| **real source mutation rounds** | **23** |

23 round すべて KILLED。**うち3 round は最初 SURVIVED だった。**

M23 は報告を書きながら見つけた穴である——「commit したのに投影の口へ
1件も渡らない」。`pending` ですら無いので retry でも拾えない。

- M10 は**本物の置物**だった（表と実装のずれを1本も検査していなかった）
- M6 は**冗長な守り**を壊していた（判断を1箇所へまとめてから再実行）
- M1 は対象テストの指定が狭かった

---

## Visual — **実施した**（019A/019B の `UNVERIFIED` を解消）

`docs/visual-evidence/FORGE-019C/manifest.md`

本番の `RevisionService` が出した文書を **Flutter で実描画し、Chromium で
撮り、画像を開いて目で確認した。**

結果: overlap / overflow / clipping / alignment / spacing 問題なし。
「残高をもっと目立たせて」の後、**残高が最大・濃色になり、収入は
`finance.income` へ降りた**——意図どおり。

### 019A/019B の `UNVERIFIED` の理由は誤りだった

「この環境に Flutter SDK が無い」と書いてあったが、**`/opt/flutter` に
Flutter 3.44.9 stable が入っている。** 確認せずに書いていた。

### 途中で真っ白なPNGを1回作った

engine 未起動のまま撮っており4枚とも真っ白だったが、**コマンドは成功して
見えた**。画像を開かなければ「実描画の証拠」として提出していた。
`AGENTS.md` の「PNGを生成しただけを Visual Review と呼ばない」は
この形の失敗を指している。

再現用に `scripts/capture_visual_evidence.py` を追加した（PowerShell 版と
違い、この環境で動く）。

---

## 見つけた製品側の問題（未修正）

**Web build に同梱フォントが無い**（`TECH_DEBT.md` TD75(b)）。

`pubspec.yaml` に `fonts:` が無く、`fontFamily: 'Helvetica'` である。
Flutter Web(CanvasKit) は system font を使わないので、
`fonts.gstatic.com` へ届かない環境では**文字が1文字も表示されない**。
「遅い」ではなく「何も出ない」という壊れ方をする。

撮影時はフォントを差し替えて回避したが、**製品側は直っていない。**

---

## UNVERIFIED

- **実 Local Model**（runs 0。環境要因、上記）
- **実 Web への往復**（Search Provider 未設定・proxy 拒否。単体テストのみ）
- **実 Cloud Provider への往復**（実APIを呼んでいない）
- **プロセス再起動を跨ぐ replay / outbox**（in-memory。安全側に壊れる）
- **複数プロセスでの直列化**（プロセス内 lock のため）
- Visual の**字形**は本番と違う（撮影時にフォントを差し替えたため）。
  配置・重なり・はみ出し・階層は確認済み

---

## Technical Debt（増減）

**解消**: advance 失敗時の atomicity / `admit`と`record`の間の前提 /
`publish()` の差し替え点（半分）。

**新規**: TD80 Outbox が NOT DURABLE / TD81 replay 予約がプロセス内 /
TD82 lock がプロセス内 / TD83 意味的操作の実装が1件 / TD84 020 の各層が
本番未配線 / TD75(b) Web build に同梱フォントが無い。

---

## FORGE-020A1 / QG-V2-R4 — 生成経路そのものを変えた（2026-08-26）

`docs/reports/FORGE-020A1-QG-V2-R4-report.md`（全文）
`docs/visual-evidence/QUALITY-GATE-V2/round-4/manifest.md`（絵の判定）

### TD87 も TD89 も解消した

以前の本番経路は**1つの単語がアプリ全体を決めて**いた。

```
Need → keyword → Domain → Template/Compiler → checklist
```

入れ替えた経路:

```
Need → Semantic Role Extraction → Capability Decomposition
     → Capability Plan → IR Generation → Forge Language → Validator
```

**キーワード表は無くしていない。変えたのは表の権限である。**
語は **1つの役**を埋めるだけで、構造は役の**組み合わせ**から決まる。

規則は1つ:

> **ACTOR と CONTEXT は、作るものの構造を決めてはならない。**

「子ども」は actor、「旅行」は context。だから体重・身長も持ち物リストも
出なくなった（**実描画で確認**）。

### Round 4 の実測

**32枚に重複が1枚も無い。** 第3回では analytics / game / study が
全 viewport で**バイト単位一致**していた。

| Need | Shape | 名前 | 記録するもの |
|---|---|---|---|
| 子どもが朝の支度を… | checklist | 支度 | （記録しない） |
| 今日やる作業を… | checklist | やること | （記録しない） |
| 旅行の写真を… | record_log | 写真記録 | 写真 / 日付 / メモ |
| 釣った場所を… | record_log | 魚 | 魚 / 場所 / 種類 |
| 植物を育てながら… | record_log | 植物 | 植物 / 音 |
| 毎日の収入と支出を… | +total | 家計簿記録 | （Curated 維持） |
| 部署ごとの売上を… | +group_compare | 売上記録 | 部署 / 金額 |
| 英単語を出題して… | +trend | 単語 | 単語 / 正解率 |

**専用 Template は1つも作っていない**（`kids_template` 等）。
`PlanShape` は5値で、Shape 名に need 由来の語が入らないことをテストが固定。

### それでも Golden Gate は FAIL（理由が変わった）

1. **ゲームがゲームではない**（TD90、最大）。Plan は `simulate.loop` と
   `media.compose` を MISSING と**正しく名指ししている**のに、
   **その事実が利用者に一切届かない**。Forge は知っているのに黙っている
2. record_log 系の入口が似ている（3タブ CRUD + フォーム、TD91）
3. 集計・推移は**文書に実在する**が一覧タブなので静止画に写らない（TD92）。
   **「撮れていない」と「無い」は違う**

### Level 0 の計測契約を直した（020A1 A〜D）

- **A** 既定 probe が Curated へ落ちていた（AI を1回も呼ばずに 200 が返る）。
  合成が要る probe に変え、実行の前後で確認。Curated なら
  `INVALID_PROBE`——**Local Model の FAIL ではなく測定の不成立**
- **B** Task を `FORGE_LANGUAGE_UPDATE` と手で書いていた。本番は
  `COGNITIVE_STAGE`。`ExperienceRecord` から**観測**するようにした
- **C** Level 0 = 経路が通ること。BenchmarkRun / PromotionGate は
  **Level 0.5** へ分けた。1件成功で PROMOTED にしない
- **D** `/v1/models` の `id` を digest 扱いしていた。**名前は重みの識別子
  ではない**。`WeightIdentity` を分け、digest は Level 0.5 の条件へ

### Machine-Independent Policy

`docs/MACHINE-INDEPENDENT-POLICY.md` / `scripts/forge_doctor.py`。

**常設の実行PCを仮定しない。** 共有状態は GitHub だけ。
作業開始時に `python scripts/forge_doctor.py` で、そのPCで何が測れるかを
**読むだけで**調べる（インストールも設定変更もしない）。

このPCの実測: テスト◯ / 実描画◯ / GitHub◯ / **model取得✗ Level 0✗**。

### Capability Plan の結論が durable Evidence へ残る

`GenerationRecord.capabilities` は013から在ったが**本番から一度も埋まって
いなかった**。R4 で埋まるようになった。

    植物を育てながら… → view.list, partial:record.sound,
                        unsupported:media.compose, unsupported:simulate.loop

**「持っていなかった」も残す。** 出来たことだけ記録すると、Forge は
自分の限界を学べない。`decision_trace` の文字列ではなく
`CognitiveContext` 経由で渡している（書式依存を避ける）。

### 配線破壊試験 18件 — 置物を2件見つけた

M11（ACTOR/CONTEXT から Entity を作る）と M17（`/v1/models` の `id` を
digest 扱いへ戻す）が**最初生き残った**。

* M11: `_subject_of()` を守っていたのは**表の中身**であってコードでは
  なかった。コード側でも除外し、静的検査を足した
* M17: 「名前は digest ではない」規則は Evidence 型でしか固定されて
  おらず、**嘘は入口（script の probe）で入る**。入口を直接見るテストを
  足した

どちらも再試験で落ちるようになった。

---

## Generated UI Quality Gate v2 — 第1回〜第3回を実施した（2026-08-26）

`docs/visual-evidence/QUALITY-GATE-V2/manifest.md`

本番の `/generate` で **8 アプリ**を生成し、**同じ Renderer** で
**4 viewport × 8 = 32 枚**を実描画・撮影し、**全部開いて**評価した。

> ### Golden Quality Gate: **FAIL**
>
> 崩れているから落ちたのではない。**同じ画面しか出てこないから**落ちた。

### 8 アプリが 3 種類の画面にしかならない

| 画面 | アプリ |
|---|---|
| tracker（21 widget型） | finance |
| tracker（20 widget型） | map |
| **checklist（7 widget型）** | **worklog / kids / photo / game / analytics / study** |

**6 アプリが構造的に同一。** 実描画でも、データ分析アプリと子ども向け
アプリが**同じチェックリスト2行**になり、違うのは追加ボタンの色だけ
だった。

overlap も overflow も無いので、**v1 の基準なら通ってしまう。**
Quality Gate v2 が要る理由がここにある。

### 実バグを1つ見つけて直した（再描画で確認）

`date_field` のラベルを入力欄の**上枠線が貫通**していた
（全 viewport で再現）。`InputDecorator.isEmpty` の既定 `false` を
渡していなかったため、空でもラベルが浮いていた。

**019C の Visual Review では見つからなかった。** あのときは同じ家計簿でも
「一覧」タブしか見ておらず、`date_field` を含む「追加」タブを描いて
いなかった。**1画面だけ見て「実描画を確認した」と言っていた**ことになる。

### 13 軸: PASS 2 / FAIL 9 / 要修正 1 / UNVERIFIED 1

主な FAIL: hierarchy / typography / density / empty-state /
long-text（**生の要求文をアプリ名にしている**）/ navigation /
visual identity / content fit（desktop で入力欄が 1950px 幅）。

### 第2回: 落ちた軸を直して、撮り直して、もう一度評価した

**測って終わりにしない**（spec §8 E→F→G）。4件直し、**すべて再描画で
確認**した。`before/` = 第1回、`after/` = 第2回。

| 軸 | 第1回 | 第2回 | 直した場所 |
|---|---|---|---|
| overflow / clipping | FAIL | **PASS** | `widget_registry_v1_7.dart`（`isEmpty`） |
| content fit | FAIL | **PASS** | `forge_renderer.dart`（本文 max 720px） |
| long-text resilience | FAIL | **PASS** | `forge_renderer.dart`（見出し2行） |
| empty-state quality | FAIL | **PASS** | `providers.py` + `compiler.py`（偽の中身をやめた） |

#### 「中身が嘘だった」が一番たちが悪かった

第1回は `最初の項目` / `2つめの項目` という**Forge の内部語**が
2件入った状態でアプリが開いていた。直したら、今度は

* 「部署ごとの売上を月別に集計してグラフで比べたい」
* 「植物を育てながら音を組み合わせるゲームを作りたい」
* 「英単語を出題して、正解率の推移を見たい」

の**すべてが牛乳・卵・パンで始まった**。

Planner が概念を1つも取り出せないとき `data_needed: ["item"]` を
差し込み、Compiler がそれを「品物 → 牛乳・卵・パン」と読んでいた。
`item` は語彙ではなく**何も分からなかったときの内部の既定値**である。
分からないものを楽観側へ倒していた（`CLAUDE.md` §3）。

分からないときは例示せず**空状態を見せる**ようにした。
**本物の買い物アプリは牛乳・卵・パンのまま**（`買い物リストを作りたい`
で確認）——分かるときは今までどおり出す。

> 同じ穴の2度目である。#29「mockの品質: 内部識別子を出さない」で一度
> 直したが、**fallback 経路だけ残っていた**。

#### 自分の判定を1件撤回した

第1回で「touch target が約24px」と書いたのは**誤り**である。
`IconButton` の既定タップ領域は 48px あり、私は**グリフを測って
タップ領域を測った気になっていた**。スクリーンショットに写らないものを
写真から判定していた。manifest に訂正を残した。

### それでも Golden Quality Gate は **FAIL**

| | Golden Quality Gate |
|---|---|
| 第1回（修正前） | **FAIL** |
| 第2回（修正後） | **FAIL**（改善したが、まだ「使いたい」とは言えない） |

**8アプリが3種類の画面にしかならない**ところは変わっていない。
Renderer をいくら磨いても、出てくる画面が2種類しかない限り通らない。

### 第3回: 名付けを生成の一部にした（修正1を完了）

`Intent.goal`（＝文）を**そのままアプリ名にしていた**のをやめた。
`forge_ai/core/naming.py` を新設し、compile の**2経路とも**通した。

候補を上から `is_name_like()` へ通し、最初に通ったものを名前にする。

| | 出所 | 例 |
|---|---|---|
| 1 | AI が名付けたもの | — |
| 2 | 取り出せた概念のラベル | 家計簿記録 / 釣果記録 |
| 3 | Domain の日本語名 | やること / 買い物 |
| 4 | **どれも通らない** | **新しいアプリ**（分からなかったと認める） |

**願望文から名詞句を削る処理は1つも足していない。削らずに落とす。**
「残高を見たい」→「残高を見」のような半端に壊れた名前を作らないため。

実測（AppBar に出た文字列）:

    毎日の収入と支出を記録して残高を見たい      → 家計簿記録
    今日やる作業を登録して、終わったものを…     → やること
    釣った場所を地図に残して魚の種類を記録したい  → 釣果記録
    買い物リストを作りたい                → 買い物リスト（変わらず）
    部署ごとの売上を月別に…                → 新しいアプリ
    植物を育てながら音を組み合わせるゲーム…     → 新しいアプリ
    英単語を出題して、正解率の推移を見たい      → 新しいアプリ

配線破壊試験 6件すべてで対応テストが落ちた（置物なし）。
`backend/tests/test_generated_app_naming.py` が**本番の HTTP** を叩き、
撮影対象と同じ8 Need で名前を見る。

### 直した結果、見えたもの（両方報告する）

**(a) 名前が自信を持って間違えるようになった（TD89、新規）。**

| 要求 | 実際に作られたもの |
|---|---|
| 子どもが朝の支度をひとつずつチェックできるようにしたい | 「こどもの成長」＋体重測定・身長測定 |
| 旅行の写真を日付ごとに残してメモを付けたい | 「旅行」＋充電器・着替え・歯ブラシ |

名付けの失敗ではなく **Domain 判定の失敗**である。第2回までは要求文が
タイトルに出ていたので、画面が要求とずれていても**タイトルだけは正しく
見えていた**。それが誤判定を隠していた。
**隠れている不具合より、見えている不具合の方がよい。**

**(b) analytics / game / study が全 viewport でバイト単位一致した。**
悪化ではない。元から同じだったものが、飾り（要求文のタイトル）が取れて
見えるようになっただけである。

### 残っている2件

| | 内容 | なぜ残っているか |
|---|---|---|
| **5** | **checklist へ落ちる範囲が広すぎる**（TD87） | **これが本体。** `LEARNABLE-LOCAL-AI-VISION.md` §22 Capability Registry 作り直しと同じ根 |
| **6** | **Domain 判定が外れる**（TD89） | 判定が「子ども」「旅行」等の substring 一致である（`lexicon.py`）。**何についての道具かではなく、どの語が出たかで決めている。** TD87 と同じ根 |

## いまの状態（2026-08-26）

**中断であって、完了ではない。** 止めた時点の状態を正直に書く。

### このセッションで終わったもの

| | 状態 |
|---|---|
| 019C Revision Atomic Closure | ✅ 実装・テスト・mutation・CI |
| 020 基盤（Agent / Web / Episode / Teacher / Gym / Novel / Dataset） | ✅ 契約 + テスト（本番配線なし。それは意図どおり） |
| Visual Review（実描画・目視） | ✅ **8アプリ × 4 viewport × 2回**（第1回 32枚 / 第2回 32枚） |
| Vision / Generative Software Direction 文書 | ✅ 記録済み |
| **020A Level 0 の準備** | ✅ 経路・計測契約・実機用 runner |
| **Real Local Model 実測** | ⬜ **別実機待ち**（CEO決定） |
| **Generated UI Quality Gate v2** | ⚠️ **第1回〜第4回まで実施。TD87・TD89 は解消。Golden Gate は FAIL**（残りは TD90〜TD92） |
| **Need→構造の経路（R4）** | ✅ Semantic Role → Capability Plan → IR。専用Templateは0件 |
| **Level 0 の計測契約（020A1）** | ✅ probe / task / scope / digest の4件を修正 |
| **Machine-Independent Policy** | ✅ 文書 + `forge_doctor.py` |

### 次の Agent がすぐ着手できるもの（実モデル不要）

1. **TD87 / TD89 — どちらも「何を作るか」の話であり、同じ根**。
   Renderer 側で直せるものは第2回・第3回でやり切った。
   `docs/spec/GENERATED-UI-QUALITY-GATE-V2.md` §8 の E→F→G は
   **2周した**（第2回・第3回）。次の周は Capability 分解に手を入れないと
   絵が変わらない
2. **§22 Capability Registry の作り直し**
   — Registry は在るが Widget と 1:1 の人手維持。生成的 primitive
   （Scene / Entity / State Machine / Grid / Drag / Game Loop）が無い
3. **§26 能力単位の Dataset** / **§33 学習イベントの網羅**
4. **TD75(b) Web build の同梱フォント**
   — Quality Gate v2 でフォントを触るなら先に決める必要がある

### 別実機でやること（Level 0）

```
ollama serve && ollama pull qwen2.5:1.5b-instruct
export FORGE_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
export FORGE_LOCAL_MODEL=qwen2.5:1.5b-instruct
python scripts/verify_local_model_level0.py
```

**PASS したときだけ** Level 0 を UNVERIFIED から動かす。
この container で走らせると `FAILED` になる——それが正しい。

## Next task

**TD90 — 作れないと分かっているのに、利用者へ言わない。**

Round 4 の Golden Gate が FAIL である最大の理由。
`CapabilityPlan.unsupported` は既に `simulate.loop` / `media.compose` を
名指ししている。**Plan まで来ているものを、会話か画面に載せるだけ**である。
新しく作るものは少ない。

その次に TD91（record_log 系の入口が似ている）と
TD92（撮影ハーネスが第1タブしか写せない）。

並行して **FORGE-020A — Real Local Model Runtime**（別実機待ち）。
Level 0 が通れば

```
LocalModelProvider（既存・OpenAI互換）
  → Provider Registry（既存）
  → AIRouter（既存）
  → BenchmarkRun
  → LocalPromotionGate（既存・配線済み）
  → routing evidence
```

まで**Provider を1つ足すだけ**で通る。並行 architecture は作らない。

その後: 020B Tool-Using Local Agent の本番配線 → 020C Episode 拡張 →
020E Novel Benchmark の初回 run。

## Next three moves

1. **CI を green にする**（runner 未割当。§CEOへの依頼 1）
2. TD90（作れないものを利用者へ言う）→ 再描画 → Round 5
3. 別実機で `forge_doctor.py` → Level 0 を走らせ、`Real Local Model runs`
   を 0 から動かす
