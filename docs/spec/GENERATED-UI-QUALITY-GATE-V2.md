# Generated UI Quality Gate v2

> **出典**: CEO 指示（2026-08-26）。**次タスクの仕様。まだ実装していない。**
>
> 上位: `docs/PRODUCT-DIRECTION.md` →
> `docs/GENERATIVE-SOFTWARE-DIRECTION.md` → この文書

**状態: ⬜ NOT IMPLEMENTED**（このセッションでは記録のみ）

---

## 1. 何をする Gate か

**同じ Renderer / Design Language** で、性格の違う **5〜10 種類**のアプリを
実生成し、実描画して評価する。

Widget や Template を増やすのではない。**同じ土台がどこまで通用するか**を
測る。1つのドメインで綺麗に出ることは、他でも綺麗に出ることを意味しない
——いま Forge が実描画で確かめているのは**家計簿1種類だけ**である
（`docs/visual-evidence/FORGE-019C/`）。

## 2. 対象アプリ（性格を散らす）

| | 狙い |
|---|---|
| 家計 | 数値中心・符号・集計 |
| Todo / 業務 | 状態遷移・チェック・一覧の密度 |
| 子ども向け | 大きい字・強い色・少ない情報量 |
| 写真中心 | 画像が主・文字が従 |
| 地図 / 探索 | 位置・空間・現在の能力では `unsupported` になりうる |
| ゲーム風 | 動き・シーン・同上 |
| データ分析 | 表・グラフ・情報密度が高い |
| 学習アプリ | 出題と回答・進捗 |

**専用 Template を用意して通すのは禁止**（`GENERATIVE-SOFTWARE-DIRECTION`
§2 / §7）。作れないものは `unsupported` と正直に記録する。

## 3. Viewport

```
390 x 844    (mobile)
320 x 640    (small mobile)
tablet
desktop
```

4 viewport × 5〜10 アプリ = **20〜40 枚**を実描画する。

## 4. 評価軸

```
hierarchy            typography          spacing
density              contrast            empty-state quality
long-text resilience navigation clarity  touch target
visual identity      content fit         accessibility
overflow / clipping
```

## 5. 「崩れていない」を PASS にしない

これがこの Gate の要点である。

現在の Visual Evidence（019C）で確認したのは
**overlap / overflow / clipping / alignment / spacing** ——
つまり「**壊れていないこと**」である。それは下限であって、品質ではない。

v2 が問うのは:

- 情報の**優先順位**が見て分かるか
- 文字が**読める大きさ・コントラスト**か
- 空のときに**何をすればいいか**分かるか
- 長い文字列を入れても**破綻しない**か
- 押せるものが**押せる大きさ**か
- そのアプリらしい**佇まい**があるか

## 6. Golden Quality Gate（最終判定）

> **人間が「このまま普通のアプリとして使いたいと思えるか」**

これを最終 Gate にする。

* 自動チェックは**下限**であって合格ではない
* `flutter test` が緑でも Visual PASS ではない（`AGENTS.md`）
* **PNG を生成しただけを Visual Review と呼ばない**
* 人が実際に画像を開いて判断した記録が要る

## 7. 実装するときの注意（この環境で分かっていること）

019C の撮影で踏んだ穴。**同じところで詰まらないように残す。**

1. **CanvasKit が CDN から取れないと engine が起動せず、真っ白な PNG が
   できる。** build が吐いた `canvaskit/` を指すこと
2. **既定フォント(Roboto)が取れないと文字が1つも描かれない。**
   しかも engine 初期化が font 取得の時間切れまで終わらないので、
   固定待ちでは間に合わない（`flutter-view` の出現を待つ）
3. **どちらも「撮れてはいるが何も写っていない」形で失敗する。**
   画像を開かない限り気付けない
4. Web build に**同梱フォントが無い**（`TECH_DEBT.md` TD75(b)）。
   v2 でフォントを増やすなら、ここを先に決める必要がある

既存の道具:

* `scripts/capture_visual_evidence.py` — 撮影（2 viewport 対応。
  v2 では tablet / desktop を足す）
* `scripts/export_revision_visual_fixture.py` — 本番から fixture を出す
* `frontend/lib/forge_019_visual.dart` — 撮影用ハーネス

## 8. 見積もりと段取り（案）

| | 内容 |
|---|---|
| A | 5〜10 アプリの Need を決め、**本番の `/generate`** で実生成する |
| B | 撮影ハーネスを N アプリ × 4 viewport へ広げる |
| C | 実描画・撮影 |
| D | **人が全部開いて**評価軸ごとに記録する |
| E | 落ちた軸を直す（Design Language / Renderer 側） |
| F | 再撮影・再評価 |
| G | Golden Quality Gate の判定を記録する |

D と F を飛ばしたら、この Gate は成立しない。

## 9. やらないこと

- 専用 Template を足して通す
- Widget を増やして「対応した」と言う
- 自動チェックが緑なだけで PASS にする
- 撮影したが開いていない画像を証拠にする

---

## 付則: Evidence の versioned path（R4 で追加、2026-08-26）

**撮り直しで既存の証拠を上書きしない。**

```
docs/visual-evidence/QUALITY-GATE-V2/
  before/     第1回
  after/      第2回・第3回   ← **共用してしまった。記録上の弱点**
  round-4/    第4回          ← ここから versioned
  round-N/    以降
```

第2回と第3回が `after/` を共用しているため、第2回の絵はもう残っていない。
**同じ過ちを繰り返さないよう、Round 4 以降は `round-N/` を必ず作る。**

各 round は自分の `manifest.md` を持ち、前 round への相対リンクで
系譜を繋ぐ。

## 付則: 「撮れていない」と「無い」を分ける（R4 で追加）

Round 4 で、`analytics.json` に `bar_chart` と
`metric_view(aggregate=sum)` が**実在する**のに、一覧タブにあるため
静止画へ写らない、という事象が起きた。

**撮影ハーネスの限界を、生成物の欠落と読み違えてはならない。**
manifest には次の3つを分けて書く。

| 記述 | 意味 |
|---|---|
| 無い | 生成物に存在しない |
| **撮れていない** | 存在するが、この撮り方では写らない |
| UNVERIFIED | そもそも測っていない（contrast 等） |
