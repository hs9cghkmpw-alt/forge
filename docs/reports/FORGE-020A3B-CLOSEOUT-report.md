# FORGE-020A3B — CLOSEOUT INTEGRITY AND CI RECOVERY

- Task: FORGE-020A3B（CEO指示、2026-08-27。スマホから）
- Branch: `claude/forge-master-handoff-k46jns`
- 前段: `FORGE-020A2-QG-V2-R5-report.md` / `FORGE-020A3-report.md`

---

## 0. まず、指示書の前提を1つ訂正する

指示書は次を前提にしていた。

> 現在確認済みHEAD: `a6ce369ec64d65df0759926c55b014d8fe6e9377`
> 現在HEADはCI FAILUREです（run 33050346292、backend 8 failed）

**その HEAD はもう最新ではない。** 指示を受け取った時点で:

| | |
|---|---|
| 最新 HEAD | `77d1a05`（`a6ce369` の3つ先） |
| CI run | `33064545042` |
| 結果 | **4 jobs すべて success** |

`a6ce369` を含む 020A3 の3 commit（`8ca31a7` / `a6ce369` / `df42dbf`）は
**いずれも backend テストが赤**だった。`77d1a05` はその赤を含めて解消
した merge commit である（020A2/R5 と 020A3 の統合）。

したがって **§1「CI FAILUREを直す」は着手時点で完了していた。**
ただし「テストを削除・skip して Green にしない」「昔の動作へ戻さない」
という条件を満たしているかは別問題なので、**そこは実際に確認した**
（§1）。

§2〜§5 には**本当に未着手のものがあった**ので、それを実装した。

---

## 1. §1 — CI failure A / B / C の実態

| 指示書の記述 | 実態 |
|---|---|
| A. `KeyError: 'result'`（GAME_NEED） | 020A3 は critical missing で `needs_confirmation` を返し生成を止めていた。merge で「止めずに伝える」形にしたので `result` が返る。テストは削除も skip もしていない |
| B. `KeyError: 'app'`（同系） | 同上。8つの Need すべてが文書を返す |
| C. `record.photo` と `partial:record.photo` が同時に legacy へ入る | **本当に残っていた。** ID は `data.photo` だが同じ事故。§5 で直した |

### 「CRUD を完成品として返す」へは戻していない

ゲームの本番応答（実測）:

```
status            success
quality.release_ready   false        ← 「仕上がっている」と言わない
capability_gap.critical ["effect.media_compose", "simulate.loop"]
capability_gap.blocks_completion  true
capability_gap.message  「音や画像を合成する・時間を進める・ゲームとして
                        動かすは、いまの Forge ではまだ作れません。…
                        植物・音を記録するところまでなら作れます。」
```

**作れないことを名指しで言い、仕上がっていないと宣言し、それでも
作れる範囲は渡す。** これが merge のときに選んだ形である（理由は
`FORGE-020A2-QG-V2-R5-report.md` §13）。

---

## 2. §2 — Quality Gate を Need の種類で分けた

Need ごとの特別扱いはしない。**振り分けは述語1つ**である。

```
capability_gap.blocks_completion
```

| Need の種類 | 見るもの |
|---|---|
| build 可能 | 生成された文書の品質（従来どおり） |
| critical missing を含む | **完成品を偽って返していないか** |

後者で見る3点（`test_forge_020a3b_quality_gate_truthfulness.py`）:

1. `release_ready` が false で、**しかもその理由が capability gap**
2. 欠けた capability の **id** が出ている
3. 利用者向けの**言葉**で説明があり、**内部 ID を含まない**

### 置物テストを1つ書いて、書き直した

最初 `release_ready is False` だけを見ていた。**配線破壊試験で通って
しまった**——`release_ready` は Design Critic の点数でも落ちるので、
gap → release_ready の配線を外しても false のままだった。

`required_fixes` に gap の文言が入っていることまで見る形へ直した。
外すと落ちることを確認済み。

また、本番に Need 名の分岐が無いことを静的に固定した
（`植物` / `ゲーム` / `game_response` 等の語が
`prompt_pipeline.py` に無いこと）。

---

## 3. §3 — Level 0 の structure_provider 独立検査（**最重要。本当に穴だった**）

### 何が抜けていたか

020A3 は `structure_source` / `structure_provider` / `structure_task` を
分けた。ところが **`RealLocalModelRun` は `structure_provider` も
`structure_task` も持っていなかった。**

Level 0 の判定は `structure_source` しか見ていない。
`AI_ENTITY_SYNTHESIS` が言っているのは「**AI が**構造を設計した」まで
である——**Cloud が設計した実行も、Test Double が設計した実行も、同じ値
になる。**

つまり **Cloud の成果が Local Model の実績として Level 0 に数えられる
状態だった。** 019B §4 / 020A で2回踏んだ「呼んでもいない Provider の
手柄」と同じ形である。

### 直した形

`RealLocalModelRun` に2欄を追加し、`why_not_counted()` で要求する。

| 条件 | 意味 |
|---|---|
| `structure_source == AI_ENTITY_SYNTHESIS` | どの段が作ったか |
| **`structure_provider == LOCAL`** | **誰が**作ったか |
| **`structure_task == entity_synthesis`** | どの stage が作ったか |
| **`entity_synthesis in observed_tasks`** | その stage が**実際に通った**か |
| `generation_source == LOCAL_AI` | 文書を作ったのが Local Model か |
| `deployment == LOCAL` | LOCAL で走ったか |
| `validator_passed` / `generation_evidence_uid` / `verification == REAL` | 従来どおり |

`entity_synthesis` は `ForgeTask.ENTITY_SYNTHESIS` から引いている
（それらしい文字列で通せないようにするため）。

script（`verify_local_model_level0.py`）も Evidence Store から
2欄を運ぶようにした。**取れなければ既定（`NONE` / 空）のまま**である
——「記録し損ね」を「Local だった」へ倒さない。

### Provider を source の別名にしない

020A3 の `StructureProvenance` には `LOCAL_AI` / `CLOUD_AI` /
`TEST_DOUBLE` が `AI_ENTITY_SYNTHESIS` の**別名**として入っていた。
それは Provider を source の中へ畳み込むことであり、**分けた意味が
無くなる。** merge のときに外してあるので、戻ったら落ちるテストを
置いた。

### Mutation（全件、対応するテストが落ちることを確認）

| # | 壊したもの | 結果 |
|---|---|---|
| M1 | `AI_ENTITY_SYNTHESIS` + provider `CLOUD` | Level 0 **FAIL** |
| M2 | `AI_ENTITY_SYNTHESIS` + provider `TEST_DOUBLE` | **FAIL** |
| M3 | `generation_source=LOCAL_AI` でも provider `CLOUD` | **FAIL** |
| M4 | Evidence の `structure_provider` 配線を外す | test **FAIL**（6件） |
| M5 | `structure_task` が `entity_structure` / 空 / 未観測 | **FAIL** |

**Real Local Model runs = 0 のまま。** 実測していないので増やしていない。

---

## 4. §4 — Canonical Capability ID

### `interact.notify` は既に無い

指示書が疑っていた「catalog は `effect.notify` なのに Plan は
`interact.notify` を作る」は、**020A2 の SoT 統一で既に解消済み**
だった。現在 `interact.notify` はテストの**禁止語**としてしか出てこない。

### 未知 ID を MISSING へ倒すのをやめた（**これは残っていた**）

`_classify()` は Catalog に無い ID を **MISSING** にしていた。
一見安全だが、実際に起きているのは**綴り間違い**か**足し忘れ**である。

黙って MISSING になると3つ壊れる。

1. 利用者へ「それは作れません」と**嘘**を言う
2. `capability_gap` の説明文に内部 ID が出る
3. Catalog への追加漏れが**永久に気付かれない**

→ `UnknownCapabilityError` を送出する。

### 成分を置物にしない（**これも残っていた**）

`_capabilities_used()` は `fields` / `views` / `interactions` しか
読んでいなかった。**`effects` と `structure_capabilities` は Plan に
ありながら Evidence へ一度も届いていなかった。**

`effect.*` は8件とも未実装なので実際には空である。
**空だから落としてよいわけではない**——1つ実装された日に「ここへ足す」
のを忘れないための配線である。両方を読むようにし、
**成分を1つでも落としたら落ちる**テストを置いた。

### namespace は責務ごと

| 成分 | namespace |
|---|---|
| `fields` / `structure_capabilities` | `data.*` |
| `views` | `view.*` |
| `interactions` | `interact.*` |
| `effects` | `effect.*` |
| 実行時のふるまい | `simulate.*` |

Catalog 側でも「層（`CapabilityLayer`）と namespace が一致すること」を
機械が検査する。

> **綴りについて（CEO へ）**
>
> 指示書は fields を `record.*`、合成を `media.*` と書いていた。
> それは **020A3 branch の綴り**であり、merge 済みの正典は `data.*` /
> `effect.media_compose` である（020A2 が採用し、`77d1a05` で確定）。
>
> 指示の**要件**は「責務ごとに namespace を分ける」「全 ID が Catalog に
> ある」であり、それは満たしている。**綴りを `record.*` / `media.*` へ
> 揃え直すかは CEO の判断**なので、勝手にはやっていない。
> やる場合は機械的な rename で、上記の invariant テストが守る。

---

## 5. §5 — PARTIAL を「成功」として学習させない

### 実態（直す前）

```
capabilities: ['data.date', 'data.entity', 'data.photo', 'data.text',
               'interact.edit', 'partial:data.photo', 'view.list']
                             ↑ 素の ID と partial: が両方
```

`data.photo` は PARTIAL である——**写真そのものは扱えない。**
ファイル名やメモを文字として残しているだけである。

素の並びだけを読む Dataset Builder / Local AI は、これを
**実装済みの成功例**として読む。**出来ないことを出来ると学習する。**

### 直した形

素の ID は「**全部出来て、実際に使った**」の意味に限る。

```
capabilities: ['data.date', 'data.entity', 'data.text',
               'interact.edit', 'partial:data.photo', 'view.list']
```

不変条件（テストで固定）: **同じ ID が素と修飾つきの両方で入らない。**

### 本来の Source of Truth を文書とテストで固定した

`capabilities`（文字列の並び）は R4 以前の古い契約である。
**新しい Source of Truth は `capability_usage`**（typed）であり、
`requested` / `used` / `status` / `source` を**欄で**持つ。

`GenerationRecord.capabilities` の docstring にそう書き、
「そう書いてあること」をテストが見る（消えたら落ちる）。
Dataset Builder は接頭辞を parse せず `used_successfully` を読める。

### R4 のテストを1件、新しい契約へ更新した

`test_capabilities_are_recorded` は `view.trend` が**素で**入ることを
見ていた。`view.trend` は PARTIAL（時系列グラフは描けず、日付順の一覧と
合計で近似）なので、新契約では `partial:view.trend` だけになる。
**削除ではなく、理由を書いて更新した。**

---

## 6. 検証（LOCAL の実測）

| 対象 | 結果 |
|---|---|
| `backend` 全件 | **1884 passed / 16 skipped** |
| `forge_ai` 全件 | **585 passed** |
| `ruff`（変更した全ファイル） | All checks passed |
| QG fixture 再生成 | **文書に変化なし**（Round 5 の56枚はそのまま有効） |

配線破壊試験は §2 / §3(M1–M5) / §4 / §5 のすべてで実施し、
**外すと対応するテストが落ちること**を確認した。

### 検証区分

| 区分 | 内容 |
|---|---|
| 実測 | 上記すべて。応答は本番 HTTP から取得 |
| Test Double | 生成は `provider=mock`。実 API は呼んでいない |
| 未検証 | **Real Local Model（runs = 0）**。実機を触っていない |

---

## 7. 残したもの

- **綴りの統一**（`data.*` → `record.*` / `effect.media_compose` →
  `media.compose`）は CEO 判断待ち。要件自体は満たしている
- **TD95**（「日付ごと」「月別」「出題」が `requested` に載らない）は
  未着手。§4 の invariant はこれを検出しない——**そもそも Plan に
  載らない**ので、Catalog にも gap にも現れない
