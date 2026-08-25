# FORGE-019C/020 — Revision Atomic Closure + Local Generative Intelligence Foundation

- **Branch**: `claude/forge-master-handoff-k46jns`
- **Start HEAD**: `63ad43403606c9731f76c98248a9b0e9149e94bf`
- **Final HEAD**: （末尾「最終状態」を参照）
- **Implementation Agent**: **Claude Code**
- 前 Implementation Agent: Claude Code（019B）、その前は Codex
- 日付: 2026-08-25

---

## 0. 要約

独立レビューが 019B へ挙げた A/B/C/D は**すべて実コードで再現できた**。
再現テストを先に書いて FAIL させてから直した。

そのうえで 020 の基盤を、**実 Local Model が要らない範囲**で作った。

**Real Local Model runs: 0**（§6 に理由と必要なもの）。

**Visual Review: 実施した**（019A/019B は `UNVERIFIED` だった。
`docs/visual-evidence/FORGE-019C/manifest.md`）。

---

## 1. 019C — Revision を本当に閉じる

### 1.1 再現（先に落とした）

`backend/tests/test_forge_019c_revision_closure.py` を先に書き、
実装前に **10 failed / 13 passed** だった。

| レビュー指摘 | 再現できたか | どう再現したか |
|---|---|---|
| A. advance 失敗で CORRECTED だけ残る | **再現** | `ArtifactRegistry.advance_to_revision` へ例外注入 |
| B. publish 失敗で確定済み Revision が API 失敗 | **再現** | `RevisionEvidenceStore.publish` へ例外注入 |
| C. admit と record の間に割り込む | **再現** | `advance_to_revision` の直前で `threading.Barrier` により落ち合わせ |
| D. 宣言と本番到達可能な操作が不一致 | **再現** | enum 7件に対し本番到達は1件 |

#### C の再現には2回作り直しが要った

最初は「barrier で開始を揃える」だけだった。**それでは競合しなかった**
——`admit()` も `record()` も現在の版を読み直すので、片方が先に版を進め
終えていればもう片方はそこで落ちる。つまり**壊れているのに PASS した**。

次に `admit()` の直後で落ち合わせたが、まだ足りなかった（`record()` が
もう一度読み直す）。

**版を進める直前**で落ち合わせて、ようやく確実に競合するようになった。
3回連続で同じ4件が落ちることを確認している。

> 偶然に依存するテストは、守っているつもりの置物である。

### 1.2 根本原因

019B の順序は

```
admit → RevisionRecord を stage → Feedback.record() → advance_to_revision()
                                   ↑追記専用。書いたら戻せない  ↑ここが落ちる
```

**落ちうる段が、戻せない段より後ろにあった。**

019B はこれを仕様として書いていた（「追記専用だから巻き戻せない」）。
しかし**追記していなければ巻き戻す必要も無い**。

### 1.3 Revision Unit Of Work

`backend/app/ai/runtime/revision_unit_of_work.py`

```
prepare   1バイトも書かずに、書けるかどうかを全部調べる
stage     RevisionRecord を置く（observe=False。Learning はまだ出ない）
commit    1. CAS で版を前進   ← 落ちうるのはここだけ
          2. staged Feedback を追記   ← 追記は最後
          （2 が落ちたら 1 を restore。lock 内なので誰も見ていない）
project   Learning Outbox へ（失敗しても Revision は成功のまま）
```

**Rejected before commit → 何も残らない。**
**Projection failure after commit → Revision は成功、projection は pending。**

`project()` を分けたのは、**確定の可否を「届くかどうか」に依存させない**
ためである。ネットワークI/Oを logical transaction へ押し込まない。

### 1.4 Feedback staging

`FeedbackEventLog` に `prepare_event` / `commit_event` /
`discard_staged_event` を足した。追記専用の契約は**1文字も緩めていない**
——`discard_staged_event()` は何もしない（何も書いていないため）。

単独の `/feedback` は従来どおり `append()`（prepare → commit → 投影）。

`ArtifactFeedbackService.admit()` は**削除した**。`prepare()` に置き換えた
結果、本番から呼ぶ経路が1つも無くなったためである。残せば「調べるだけの
口」と「調べて組み立てる口」が並び、片方だけ条件が緩む余地ができる
（011 §5 で踏んだ形）。

### 1.5 Artifact CAS + per-artifact lock

`advance_to_revision()` は3値すべてを照合する。

- `version_token`（世代）
- `evidence_id.uid`（系譜の位置）
- `document_binding`（中身の身元）

`version_token` だけ見ると、同じ token のまま別系譜へ差し替えられた場合を
見逃す。

**`expected` を渡さない呼び出しも conflict にした**（fail closed）。
「省略したら無条件で上書き」を残すと、その口が新しい blind overwrite に
なる。

lock は `ArtifactRegistry.lock_for(handle)`。

- global lock にしない（無関係な生成物を待たせない）
- 使用中だけ保持し、最後の1人が抜けたら捨てる（無限増殖しない）
- `finally` で必ず解放
- **同時に持つ lock は常に1つ**なので deadlock しない

### 1.6 Replay Log の予約

019B の `find → conflicting_key → remember` は **check-then-act** だった。
同じ要求が同時に2本来ると両方が本処理へ入る。

`begin()` で予約を取る形にした。2本目は1本目の完了を待ち、終わったら
同じ結果を replay する。**失敗は覚えない**（失敗を replay しない）。
待ちには上限があり、超えたら `concurrent_revision` を返す。

### 1.7 Learning Outbox v1

`backend/app/ai/gateway/learning_outbox.py`

| Contract | |
|---|---|
| identity | `(evidence 型名, uid)` |
| status | `pending` / `projected` |
| attempts | 回数 |
| last_error | **分類のみ**（例外メッセージは持たない） |
| created_at / projected_at | |

- Revision commit → outbox
- 投影成功 → `projected`
- 投影失敗 → `pending` のまま。**API は成功のまま**
- retry → **重複 Learning Event なし**（exactly-once 相当）

**保持してよい型を whitelist で固定**（`GenerationRecord` /
`RevisionRecord` / `ArtifactFeedbackEvent`）。raw text / secret /
`ArtifactHandle` / credential は入らない。投影が終われば payload を捨てる。

> **IN-MEMORY / NOT DURABLE / UNVERIFIED（再起動を跨ぐ retry）。**

### 1.8 Operation vocabulary honesty

`backend/app/ai/runtime/operation_support.py`

| 段 | 件数 | 内訳 |
|---|---|---|
| `PRODUCTION_SUPPORTED` | **1** | `select_primary_metric` |
| `ENGINE_ONLY` | 1 | `set_design_role`（型はあるが自然言語から到達しない） |
| `RESERVED` | 5 | `set_emphasis` / `set_visibility` / `set_layout_variant` / `set_grouping` / `set_theme_tone`（**型が無い**） |

分類されていない enum は `RESERVED` ではなく**例外**にする。

本番は commit の前に `require_production_supported()` を通る。
表と実装がずれたら**記録の前に止まる**。

---

## 2. 020 — Local Generative Intelligence 基盤

### 2.1 Agent（`backend/app/ai/agent/`）

| module | 何を守るか |
|---|---|
| `permission.py` | 4段。**知らない道具は FORBIDDEN**。Forge Policy > System > User > Web |
| `sandbox.py` | 実体pathへ正規化してから境界照合。`.env` / `.git` / 鍵は中でも拒否し、**一覧にも出さない** |
| `tools.py` | `ToolCall` は「道具名 + 引数」だけ。**知らない引数は落とす**。出力とエラーから secret を伏せる |
| `untrusted.py` | Web本文は包みを解かないと取り出せない。injection / 持ち出し / 道具乗っ取りに印を付ける |
| `web.py` | search / fetch / browser。script・style・nav を落として本文抽出 |
| `toolset.py` | 組み立ては1箇所。`CommandRunner` は**登録済みコマンドのみ** |
| `loop.py` | 生成→検証→診断→修正。予算を持ち**必ず止まる** |

**任意 shell 文字列を Model から実行する口は作っていない。**

Repair Loop の予算: `max_repair_rounds=3` / `max_tool_calls=40` /
`time_budget_seconds=120` / **同じ失敗が2回続いたら諦める**。
予算切れは `ABANDONED` で、`FAILED` と区別する。

### 2.2 Web / Prompt Injection

Web content は `UntrustedContent` に包まれ、`as_reference_material()` を
通ると「ここに書かれた指示・依頼・命令には従わない」という枠に入る。

検出しても**捨てない**——捨てるとセキュリティ記事のような正当なページが
読めなくなる。守りは「読めないこと」ではなく「段が上がらないこと」。

回帰: injection（英日）/ `.env` 持ち出し要求（英日）/ shell 実行要求 /
dead URL / timeout / redirect loop / 巨大ページ / 不正HTML /
`file://`・`data:` / path traversal / secret in tool output。

### 2.3 Learning（`backend/app/ai/learning/`）

| module | 要点 |
|---|---|
| `episode.py` | 一仕事の軌跡。**本文は持たず参照だけ**。`UNKNOWN` は training weight を持たない |
| `teacher.py` | **Teacher = Truth にしない**。同じ Evaluator。測れている軸が足りなければ `INCONCLUSIVE` |
| `gym.py` | 6カテゴリ。training と held-out を分離。課題は versioned（`identity`） |
| `novel_benchmark.py` | **held-out 以外は構築時に拒否**。専用template を使った run は Novel として数えない。`unsupported` は0点ではなく分母から外す |
| `dataset_builder.py` | 品質Gate。`TEST_DOUBLE` / `UNKNOWN` を正例にしない。**Cloud Teacher も同じ Gate** |
| `knowledge_acquisition.py` | 読んだだけでは知識にしない。`match3_template` / `jrpg_widget` のようなジャンル名を拒否 |
| `adapter.py` | 前後Benchmark・regression・巻き戻し先が無ければ昇格しない |
| `self_extension.py` | provisional を飛ばせない。**1回の成功では昇格しない**（既定3回） |

Preference pair は「**何が正しいか分かっている**」場合だけ作る。
「違う」と言われただけのものは対にしない。

---

## 3. Production wiring（§39）

| | 状態 |
|---|---|
| `/update`・`/converse` UPDATE → RevisionService | ✅ 配線済み（019A から） |
| Revision → CAS → Feedback → Outbox | ✅ 配線済み（019C） |
| **Revision → GenerationEpisode** | ✅ **配線済み（今回）** |
| Benchmark → LocalPromotionGate → routing | ✅ 配線済み・**昇格0件**（実測が無い） |
| Agent / Tool / Web | ⬜ **契約のみ。本番配線なし** |
| Teacher / Gym / Novel / Dataset / Adapter | ⬜ **契約のみ。本番配線なし** |
| Self-Extension | ⬜ 契約のみ |

Episode を本番へ配線したのは、「Agent が動いたときだけ記録する」形に
すると**今は1件も生まれない**からである（`evaluate_for_export()` が
テストからしか呼ばれていないのと同じ状態）。変更は本番が必ず通る。

本番 Episode の `training_use` は `UNKNOWN`。したがって
**Dataset Gate はこれを落とす**——収集してよいことは学習に使ってよい
ことではない。

未配線であることも**テストで固定した**
（`test_forge_020_production_wiring.py`）。配線したのに文書を直さないと
落ちる。

---

## 4. Tests

**LOCAL と CI を混ぜない。**

| | LOCAL（今回の実測） |
|---|---|
| backend | **1,706 passed / 16 skipped** |
| forge_ai | **521 passed** |
| Flutter test | **514 passed** |
| `flutter analyze --fatal-infos --fatal-warnings` | **No issues found** |
| `flutter build web --debug` | **成功** |
| ruff（変更ファイル） | All checks passed |
| backend smoke（起動 / health / CORS / generate） | **成功** |

CI の実測値は「最終状態」節に記す。

### guard の内訳（混ぜない）

今回追加したテストは **186 件**。内訳:

| file | 件数 |
|---|---|
| `test_forge_019c_revision_closure.py` | 23 |
| `test_forge_019c_outbox_and_cas.py` | 24 |
| `test_forge_019c_operation_support.py` | 14 |
| `test_forge_020_agent_security.py` | 55 |
| `test_forge_020_learning_assets.py` | 56 |
| `test_forge_020_production_wiring.py` | 14 |

**種類ごとに分けて数える**（混ぜない）。

| 種類 | 数 | 何を見ているか |
|---|---|---|
| behavior guards | **178** | 実際に動かして結果を見る |
| static protocol checks | **8** | enum の網羅・policy の key の形・本番から参照されていないこと・docstring |
| **real source mutation rounds** | **22** | ソースを壊して落ちることを確認 |

static protocol checks の内訳: 未分類 enum の検出 / 型の無い操作が
`RESERVED` であること / policy の key の形 / Novel の配点に Widget数が
無いこと / Router が Promotion Gate を見ること / Agent・Teacher 層が
本番から参照されていないこと（2件）/ Episode 層は参照されていること。

### mutation（§35）

22 round すべてで、ソースを壊すと落ち、戻すと通ることを確認した。

| id | 壊したもの | 結果 |
|---|---|---|
| M1 | commit 後段が落ちても版を戻さない | KILLED |
| M2 | 期待値なしの advance を通す | KILLED |
| M3 | CAS の3値比較を無効化 | KILLED |
| M4 | 生成物ごとの直列化を外す | KILLED |
| M5 | replay の予約を外す | KILLED |
| M6 | 投影済みの再投影を許す | KILLED |
| M7 | 投影失敗を握らない | KILLED |
| M8 | Outbox の型 whitelist を外す | KILLED |
| M9 | document binding の照合を外す | KILLED |
| M10 | 本番で使ってよい操作かの検査を外す | KILLED |
| M11 | 知らない道具を AUTO_ALLOW にする | KILLED |
| M12 | 権限判定の結果を無視して実行 | KILLED |
| M13 | sandbox の境界検査を外す | KILLED |
| M14 | Web の持ち出し要求検出を外す | KILLED |
| M15 | 道具出力の secret 伏せを外す | KILLED |
| M16 | training right を見ずに Dataset 候補にする | KILLED |
| M17 | Mock / TEST_DOUBLE を正例として通す | KILLED |
| M18 | training の Task を Novel に混ぜる | KILLED |
| M19 | 専用template の run も Novel として数える | KILLED |
| M20 | 1回の成功で Capability を昇格 | KILLED |
| M21 | 本番の Episode 記録を外す | KILLED |
| M22 | ジャンル専用 template を Knowledge にする | KILLED |

#### 3 round は最初 SURVIVED だった（そのまま報告しない）

- **M10 は本物の置物だった。** 「本番が届いた操作 ⊆ 表」しか見て
  いなかったので、`require_production_supported()` を丸ごと外しても
  何も落ちなかった。`ENGINE_ONLY` の操作を強制的に流し込むテストを
  足して killable にした。
- **M6 は冗長な守りを壊していた。** `submit()` と `_attempt()` の
  両方に同じ早期returnがあり、片方を壊しても動いた。**判断を1箇所へ
  まとめて**から再実行した。二重の守りは、mutation で有無を確かめ
  られなくする。
- **M1 は対象テストの指定が狭かった。** 実際には 019B の suite が
  殺していた。対象を直して再実行。

---

## 5. Visual（§37）

**実施した。** 詳細は `docs/visual-evidence/FORGE-019C/manifest.md`。

```
本番の RevisionService が出した after.json
  → flutter build web --debug -t lib/forge_019_visual.dart
  → Chromium で実描画
  → 撮影（390×844 / 320×640、DSF 2）
  → **画像を開いて目で確認**
```

結果: overlap / overflow / clipping / alignment / spacing いずれも
問題なし。hierarchy と primary metric visibility は**意図どおり**
——「残高をもっと目立たせて」の後、残高が最大・濃色になり、収入は
`finance.income` へ降りた。

### 019A/019B の `UNVERIFIED` の理由は誤りだった

「この環境に Flutter SDK が無い」と書いてあったが、**`/opt/flutter` に
Flutter 3.44.9 stable が入っている**。確認せずに書いた。

### 途中で真っ白なPNGを1回作った

engine 未起動のまま撮っており4枚とも真っ白だったが、**コマンドは成功
して見えた**。画像を開かなければ「実描画の証拠」として提出していた。

### 撮影環境の制約

`gstatic.com` が拒否されるため、CanvasKit を同梱物から読ませ、
フォントは撮影時だけローカルの IPAGothic を返した。したがって
**字形は本番と違う**。見てよいのは配置・重なり・はみ出し・階層である。

再現可能にするため `scripts/capture_visual_evidence.py` を追加した。

---

## 6. Real Local Model — **runs 0**（§13・§38）

### 実行できなかった。理由は環境である

| 必要なもの | この環境 |
|---|---|
| Ollama | **未インストール** |
| llama.cpp | **未インストール** |
| torch / transformers | **未インストール** |
| GPU | **無し**（`nvidia-smi` 無し） |
| RAM | 15 GB |
| 既存の Local endpoint | **無し**（listen している port 無し） |

### install しても取得できない

network policy の実測:

```
https://pypi.org/simple/     → 200
https://huggingface.co/      → CONNECT tunnel failed, 403
https://ollama.com/          → CONNECT tunnel failed, 403
https://github.com/          → 403
```

**モデル重みの取得先が塞がっている。** したがって「install の許可を
もらえば動く」ではない。

### 必要なもの（許可を求める前の情報）

- Runtime: Ollama もしくは llama.cpp（`llama-server`）
  - どちらも **OpenAI互換 `/v1/chat/completions`** を話すので、
    既存の `LocalModelProvider` が `base_url` だけで繋がる
    （**並行 architecture を新設しない**）
- Model 候補: `qwen2.5:1.5b-instruct`（既定値）または `qwen2.5:7b-instruct`
  - 1.5B / Q4 で **約 1.0 GB**、7B / Q4 で **約 4.5 GB**
  - RAM 目安: 1.5B で 4 GB、7B で 8〜10 GB。**この環境の 15 GB で足りる**
- 追加で必要なもの: **`huggingface.co` / `ollama.com` への到達**
  （network policy の変更。install 許可だけでは足りない）
- なぜこの方式か: Provider Registry / AIRouter / Benchmark /
  LocalPromotionGate が既に OpenAI互換前提で配線済みであり、
  **Provider を1つ足すだけで Local Promotion Gate まで通る**

### 数え方

**Mock / fake server / curated fixture を Real Local として数えていない。**

```
Real Local Model runs = 0
```

---

## 7. Security / Privacy

### Security

- Permission Broker 4段。知らない道具は `FORBIDDEN`
- sandbox: 実体path正規化 / `.env`・`.git`・鍵の拒否 / 一覧にも出さない
- 任意 shell 文字列の実行口を作っていない
- 道具の出力・エラーから secret を伏せる（**長さも先頭も出さない**）
- Web content は命令として扱わない。injection regression あり
- `file://` / `data:` は取得しない

### Privacy

- Episode / Outbox / Evidence は**本文を持たない**（識別子と分類だけ）
- Outbox の保持型は whitelist。投影後は payload を捨てる
- 本番 Episode の `training_use` は `UNKNOWN` → Dataset Gate が落とす
- `collection right ≠ training right` をテストで固定
- Screenshot Evidence は `inspected_by_human` を持ち、**撮っただけを
  確認と数えない**

---

## 8. 何が IMPLEMENTED / PARTIAL / UNVERIFIED / NOT IMPLEMENTED か

| | 状態 |
|---|---|
| Revision atomicity（advance 失敗） | **IMPLEMENTED** |
| Revision の投影分離（outbox） | **IMPLEMENTED**（ただし NOT DURABLE） |
| Artifact CAS / per-artifact lock | **IMPLEMENTED** |
| Replay 予約 | **IMPLEMENTED**（プロセス内） |
| Operation vocabulary honesty | **IMPLEMENTED** |
| GenerationEpisode | **IMPLEMENTED + 本番配線** |
| Tool / Permission / Sandbox / Web / Agent Loop | **PARTIAL**（契約 + テスト。本番配線なし） |
| Teacher / Gym / Novel Benchmark / Dataset | **PARTIAL**（契約 + テスト。run 0件） |
| Adapter / Training pipeline | **NOT IMPLEMENTED**（契約のみ） |
| Self-Extension | **NOT IMPLEMENTED**（契約のみ） |
| **Real Local Model** | **NOT IMPLEMENTED**（環境要因。runs 0） |
| 実 Web への往復 | **UNVERIFIED** |
| 実 Cloud Provider への往復 | **UNVERIFIED**（実APIを呼んでいない） |
| プロセス再起動を跨ぐ replay / outbox | **UNVERIFIED**（in-memory） |
| 複数プロセスでの直列化 | **UNVERIFIED**（プロセス内 lock） |
| Visual Review | **実施済み**（字形は本番と違う。manifest 参照） |

---

## 9. 自己監査（§45）

1. **実モデルか？** — 実モデルは1回も動かしていない。`runs 0` と書いた。
   Mock を数えていない
2. **起動しただけを完成扱いしていないか？** — 起動すらしていない。
   完成の定義（`docs/GENERATIVE-SOFTWARE-DIRECTION.md` §3）を文書化した
3. **Widget/Template 追加で伸びたふりをしていないか？** — Widget も
   Template も1つも足していない。むしろジャンル名の Knowledge 登録を
   **拒否する Gate** を入れた
4. **未知 Need への Architecture 生成へ近づいたか？** — Capability Spec /
   Self-Extension の Gate と、Novel Benchmark の採点契約までである。
   **生成そのものは未実装**
5. **Teacher を Truth 扱いしていないか？** — していない。測れている軸が
   足りなければ `INCONCLUSIVE` を返す
6. **Web を命令として信用していないか？** — していない。包みを解かないと
   本文が取り出せない形にし、mutation で確認した
7. **Episode は成功/失敗/repair を残せるか？** — 残せる。本番の Revision
   から実際に1件生まれることをテストで固定した
8. **Dataset は品質Gateを通るか？** — 通る。**本番 Episode は現状 Gate に
   落ちる**（training right が `UNKNOWN`）。それが正しい
9. **Local Promotion は実測に基づくか？** — 基づく。実測が無いので
   **昇格0件**である
10. **本番から繋がっているか？** — Revision 系は繋がっている。
    Agent / Teacher / Gym / Novel / Dataset は**繋がっていない**。
    繋がっていないことをテストで固定した
11. **生成アプリ品質と Local AI のどちらかを犠牲にしていないか？** —
    今回は生成アプリ側の記録の正しさ（019C）を先に閉じた。生成品質そのもの
    には触れていないが、劣化もしていない（visual fixture がバイト一致）
12. **難しいから目標を狭めていないか？** — 狭めていない。実 Local Model
    が動かない理由を環境として明記し、**必要なものを具体的に書いた**

---

## 10. 最終状態

（push 後に `docs/HANDOFF.md` と併せて確認すること）
