# Generated UI Quality Gate v2 — 第5回（Round 5）

- Task: FORGE-020A2 / GENERATED-UI-QG-V2-R5（CEO指示、2026-08-27）
- 詳細: `docs/reports/FORGE-020A2-QG-V2-R5-report.md`
- 第4回: `../round-4/manifest.md` ／ 第1〜3回: `../manifest.md`
- 環境: Flutter 3.44.9 stable / Chromium (Playwright) / Linux container
- 撮影: `python scripts/capture_quality_gate_r5.py <build> round-5/`

---

## 判定

| | 置き場 | Golden Quality Gate |
|---|---|---|
| 第1回 | `../before/` | **FAIL**（8アプリが3種類の画面） |
| 第2回 | `../after/` | **FAIL**（崩れは直った） |
| 第3回 | `../after/`（上書き） | **FAIL**（名前は名前になった） |
| 第4回 | `../round-4/` | **FAIL**（8アプリが8種類になった） |
| **第5回** | **`round-5/`** | **FAIL**（**初めて操作して見た**） |

**結果を先に決めていない。** ゲームは今回も普通に使いたい品質ではない
ので FAIL のままである（後述「Golden Gate」）。

---

## 第4回との違い：**押してから撮った**

第4回までは開いた直後の1画面しか撮れていなかった。第4回の manifest は
「`bar_chart` は実在するが写らない」と書いたが、**書いただけでは次も
同じ**である。

第5回は Playwright で**実際にタブを押してから**撮る。

- 14 state × 4 viewport = **56枚**（`320x640 / 390x844 / 834x1112 / 1440x900`）
- 押せなかった操作: **0件**（1件でもあれば script は exit 1 を返す）

### 「押したつもり」を2回踏んだ

**1回目（座標）。** `x = width * (index + 0.5) / len(tabs)` で押したところ、
**desktop だけ 4 件が押せなかった**。`forge_renderer.dart` は本文を
`Center` + `maxWidth: 720` で包むので、1440px でもタブ列があるのは
360〜1080 である。上の式では index 0 が x=240（余白）、index 2 が
x=1200（余白）へ落ちていた。**index 1 だけが偶然 x=720＝中央で当たって
いた。** 座標は Dart の値から読むように直した
（`backend/tests/test_forge_020a2_round5_capture.py`）。

**2回目（差分の穴）。** 「押す前と絵が変わったこと」を成功条件にして
いたが、これには2つ穴があった。

1. `InkWell` の hover は**タブが変わらなくても**絵を変える
   → 撮る前にカーソルをタブ列の外へ動かす
2. もともと選ばれているタブは押しても変わらない
   → **別のタブを経由してから戻る**。往きと帰りの両方で絵が変わることを要求する

穴1のせいで、mobile の「一覧タブ」は**タブが切り替わっていないのに
成功扱い**になっていた。

### 同じ絵が16組ある。**これは正しい**

`md5sum` で16組が一致する。内訳は
finance / analytics / study の `initial` == `summary|comparison|trend` と、
photo の `initial` == `input` である（各4 viewport）。

これは Semantic Layout Composition（TD91）が効いている証拠である。
finance/analytics/study は要約が先頭タブ、photo は入力が先頭タブなので、
**その state は開いた直後の画面そのもの**になる。経由タブを踏んで戻る
往復で「押して到達できる」ことは確かめてある。**app をまたいだ重複は
1組も無い。**

---

## 見つけて直したもの：**無言の灰色の箱**

一覧の空表示のすぐ下に、**文字が1つも無い灰色の箱**が描かれていた。
finance / analytics / study にあり、game / photo には無い。

原因は `bar_chart` である。記録が無いとき `SizedBox.shrink()` を
返していたが、`style_role: card.summary` の見た目は
`applyForgeRole()` が**外側から**被せるので、中身が空でも
**card の padding だけが残る**。被せる側は中が空だと知らない
（状態を読むのは `bar_chart` の中だけ）。

利用者から見れば「何かが壊れている箱」である。

**直した**（`widget_registry_v1_6.dart`）。空のときは見出しと
「グラフに出せる記録がまだありません」を出す——中から名乗る。

- 再描画して再評価した（この manifest の絵は**直した後**のもの）
- 戻したら落ちるテストを置いた: `frontend/test/json_ui/widget_registry/empty_bar_chart_test.dart`
- 配線破壊試験: `SizedBox.shrink()` へ戻すと1件 FAIL する（確認済み）

> **静的なテストは全部通っていた。** 撮って、開いて、見るまで
> 誰も気付かなかった。

---

## 13軸レビュー（56枚を開いて見た）

| 軸 | 判定 | 根拠 |
|---|---|---|
| hierarchy | △ | 見出し→タブ→本文は立っている。ただし metric が素の text 2行で、数値の階層が無い |
| typography | ○ | 見出し / タブ / ラベル / 補助文の4段が区別できる |
| spacing | △ | 一覧 card とグラフ card が**隙間なく接する**（角が衝突して見える） |
| density | ○ | 入力欄の高さ・間隔は詰まっていない |
| contrast | ○ | 補助文は 0.6 alpha。読める |
| empty-state | ○ | 今回直した。空の理由が全部言葉になった |
| long-text | ✗ | **320px で「家計簿記録を…」が2つ並ぶ**（追加と編集が見分けられない） |
| navigation | ○ | タブが実際に押せる。選択中が色と下線で分かる |
| touch target | ○ | タブ・入力欄・保存とも 44px 以上 |
| visual identity | ○ | finance=青 / analytics=藍 / photo・game=橙。同じ Renderer で違って見える |
| content fit | ○ | desktop で `maxWidth: 720`。1440px でも入力欄が伸び切らない |
| accessibility | △ | ラベルが placeholder 兼用。入力すると項目名が消える |
| overflow | ○ | 横スクロールは無い。切れるのは long-text の1件のみ |

### long-text（320px）の実物

`finance-initial-small-320x640.png`:

```
家計簿記録一覧  家計簿記録を…  家計簿記録を…
```

**「追加」と「編集」が区別できない。** entity 名を全タブの接頭辞に
しているのが原因である。analytics（売上記録）は同じ 320px で切れない
ので、長さの問題であって仕組みの問題ではない。→ TD94。

---

## 求められたのに出せなかったもの

`docs/evidence/quality-gate-v2/manifest.json` の `capability_gap` に
**本番の HTTP 応答から**入っている（020A2 §4/§5）。

| app | 伝えている | 伝えていない |
|---|---|---|
| photo | 写真そのものは扱えない | **「日付ごと」**（grouping が Plan に載らない） |
| game | ゲームループ・音の合成が作れない（`blocks_completion: true`） | — |
| study | 時系列グラフはまだ描けない | **「出題」**（quiz が Plan に載らない） |
| analytics | （gap なし） | **「月別」**（日付 field すら作られない） |
| finance | （gap なし） | — |

**「〜ごと」「月別」「出題」は `requested` に載らない**ので、落ちても
gap に出ない。黙って落ちている——`GENERATIVE-SOFTWARE-DIRECTION.md` が
禁じている形である。→ TD95（`view.group_by` / 出題）。

---

## Golden Gate: game は FAIL のまま

`game-initial-mobile-390x844.png` は
**「植物」「音」を入れて保存する CRUD フォーム**である。ゲームではない。

正直さの層は働いている:

```
critical: ["effect.media_compose", "simulate.loop"]
blocks_completion: true
「ゲームループと音の合成は、いまの Forge ではまだ作れません」
```

**知っていて黙ってはいない。** しかし作れてもいない。
「普通のアプリとして使いたい品質」には達していないので **FAIL**。

---

## 検証区分

| 区分 | 内容 |
|---|---|
| 実測 | 56枚の描画・タブ操作・目視。`capability_gap` は本番 HTTP 応答 |
| Test Double | 生成は `provider=mock`。**Real Local Model runs = 0**（増やしていない） |
| 未検証 | 実機（iOS / Android）での描画。実データを入れた状態の一覧・グラフ |
