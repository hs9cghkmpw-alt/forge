# Design Revision — 「見て、言って、直る」の設計案

**2026-08-18 / 実装前の提案。まだコードは1行も無い。**
**CEO指示（優先順位・原則）を受けた設計であり、承認前の案である。**

---

## 0. これは見た目の便利機能ではない

CEOの指示を、Forgeの用語で言い直す。

```
User Correction
   ↓ 意味として解釈（対象 / 不満 / 望む変化）
Semantic Design Operation
   ↓ 現在Documentへ**局所**適用
Validator / Design Critic
   ↓
Runtime
   ↓ 修正版を提示
ACCEPTED / CORRECTED Evidence
   ↓
Forge Knowledge → Local AI Improvement
```

**閉ループの最重要の辺**（TD65）がここで初めて繋がる。

いま最も価値のあるデータは、完成したDocumentではない。

```
初回生成       surface.card
利用者         「もっと浮かせて」
修正           surface.elevated
利用者         「これでいい」

→ CORRECTED: surface.card    （外した選択）
→ ACCEPTED : surface.elevated （受け入れられた選択）
```

**この対**は、完成Documentを何千個集めても得られない。
Local AIが学ぶべきは「何が良いか」だけでなく
**「何を外したか」「どう直したら通ったか」**だからである。

---

## 1. 既にあるもの（調査結果）

推測せず、実コードを読んで確認した。**土台の多くは既にある。**

| 資産 | 場所 | この機能での役割 |
|---|---|---|
| Design Language V1（33 role） | `app/ai/runtime/design_language.py` | 変更先の語彙 |
| 軸ごとの択一＋検証 | 同上 `DESIGN_CHOICE_AXES` / `is_valid_choice` | AIに自由記述させない仕組み |
| role→視覚の対応 | `frontend/lib/json_ui/renderer/design_language.dart` | 直した結果が実際に見える |
| **widget単位のrole適用** | `screen.styleRoles[node.id]` | **「このカードだけ」を実現できる** |
| Semantic Design Critic | `forge_ai/core/critic/semantic_design_critic.py` | 直した結果が壊れていないか |
| provenance | `DesignRoleDecision(axis, role, source)` | 誰が決めたかを残す |
| 態度→対比→対象の3段判定 | `capability.classify_correction()` | 「違う」の解釈（後述の限界あり） |
| `CorrectionTarget` | `capability.py` | DATA / VIEW / EFFECT / PROBLEM / ACCEPTED / UNCLEAR |
| `AcceptanceSignal` | `learning_foundation.py` | ACCEPTED / CORRECTED / ABANDONED / UNKNOWN |
| **`RevisionRecord`の設計** | `TECH_DEBT.md` TD68 | **型の設計は済んでいる（実装が無い）** |
| 承認を書き足すAPI | `note_user_acceptance(refs, signal)` | 実装済み |
| `/converse`のUPDATE分岐 | `conversation_engine.py` | 「使用中のツールがある時のみupdate」 |

### 逆に、無いもの

| 欠けているもの | 事実 |
|---|---|
| **デザインを知らないUPDATE** | `apply_update()`のプロンプトに`style_role`もDesign Languageも一言も無い。変更要求と現在のJSON全部を渡し、**AIにJSON全体を書き直させている** |
| **承認を受けるHTTP口** | `note_user_acceptance`は在るのに、**それを呼ぶendpointが1つも無い**（grep済み）。UIも聞かない（TD65） |
| **`RevisionRecord`の実装** | 型もStoreも無い（TD68） |
| **デザイン用の訂正対象** | `CorrectionTarget.VIEW`は「地図で見たい」（Capability層）を指す。「落ち着いた感じに」（Design Language層）を表せない |
| **軸が2つしかない** | `screen_density` / `list_surface`。7分類のうち2つ目の一部しか覆えない |
| **局所適用の仕組み** | 今のUPDATEは全体書き直し。patchの概念が無い |

---

## 2. 最大の設計判断 — 全体書き直しをやめる

### いまの方式の害

`apply_update()` は現在Document全部をAIへ渡し、**新しいDocument全部**を
返させている。

これは3つの理由で、この機能には使えない。

1. **消えても気付けない。** 「残高をもっと目立たせて」と言った結果、
   AIが支出のKPIを落としても、Validatorは構造しか見ないので通る。
   利用者は言っていないものを失う
2. **何を直したか分からない。** before/afterのDocument差分は取れるが、
   「どのroleをどう変えたか」という**意味の差分**にならない。
   Local AIの教師データとして弱い
3. **R1の原則と矛盾する。** R1は「AIは意味を選ぶ／値は選ばせない」に
   したのに、ここだけJSON全部を自由記述させている

### 採る方式: Semantic Patch

AIに返させるのは**Documentではなく、意味の変更指示**である。

```
DesignRevisionOperation
  target   : records_list_view      ← どのWidget/semantic target
  axis     : list_surface           ← どの軸
  from     : surface.card           ← 今の値（Forgeが埋める）
  to       : surface.elevated       ← AIが閉じた選択肢から選ぶ
```

Forgeがこれを**現在Documentへ局所適用**する。触っていない場所は
1バイトも変わらない。

**利点**:

* 残高が消える事故が構造的に起きない（触らないから）
* 「何が嫌で、何をどう直したか」がそのまま記録になる
* Validator・Criticは変更後に**もう一度**通す（Truthは変わらない）
* AI呼び出しは1回（今のUPDATEと同じ。追加コストなし）

---

## 3. 「普通の日本語」を意味へ落とす

CEOが挙げた例を、実際にどう解くかを設計する。

| 利用者の言葉 | 解釈すべきもの | 出力 |
|---|---|---|
| 「残高をもっと目立たせて」 | target=残高のWidget / 望む変化=強調↑ | axis=metric_emphasis, to=metric.primary |
| 「一覧がごちゃごちゃしてる」 | target=一覧 / 不満=情報過多 | density↑（relaxed）＋ surface整理＋表示Field削減 |
| 「このカードだけもっと目立たせたい」 | **target=特定Widget** | その1つだけ surface.elevated |
| 「赤が強すぎる」 | target=赤いもの / 不満=強すぎ | **意味の色の強度**を変える（`#RRGGBB`は書かせない） |
| 「追加ボタンが目立ちすぎる」 | target=追加ボタン / 望む変化=弱める | button.primary → secondary |
| 「もっとシンプルにして」 | **target=画面全体・複数軸** | density / surface数 / secondary情報 を総合再設計 |

### 3段階に分ける（`classify_correction`と同じ形）

```
1. 対象 (target)   どのWidget / どの画面 / 全体か
2. 不満 (complaint) 多い・強い・弱い・ごちゃつく・地味
3. 望む変化 (delta) 強調↑↓ / 密度↑↓ / 面↑↓ / 数を減らす
```

**なぜ3つに分けるか**: 「もっとシンプルに」は対象=全体・不満=情報過多で、
**複数の軸を同時に動かす**。1つの軸への択一に押し込むと表現できない。
逆に「このカードだけ」は対象が1つに絞れる。**対象の粒度と軸の数は
独立**なので、別々に持つ。

### AIに渡すもの / 渡さないもの

渡す:
* 現在Documentの**意味の要約**（widget id・type・現在のrole・階層）
* 変更可能な軸と選択肢（Design Language Knowledge）
* 利用者の言葉

渡さない・させない:
* 色コード、px、余白の数値
* Document全文を書き直す権限

---

## 4. 対象（target）の特定 — ここが一番難しい

「このカードだけ」を解くには、**利用者が見ているものとWidget idを
結びつける**必要がある。

### 3つの案

| 案 | 内容 | 判断 |
|---|---|---|
| A | 画面の意味要約をAIへ渡し、AIにwidget idを選ばせる | **採用（第1段階）** |
| B | 利用者が画面上でWidgetをタップして指す | 採用（第2段階、UIが要る） |
| C | 座標・スクリーンショットから推定 | 不採用 |

**Aを先にする理由**: UIを変えずに始められる。`records_list_view`
`records_hero_metric` のようなidは既に意味を持つ名前になっており、
type・role・ラベルを添えればAIは十分選べる見込み。

**ただし選ばせっぱなしにしない。** 存在しないidを返したら不採用、
UNCLEARとして**聞き返す**（`CorrectionTarget.UNCLEAR`と同じ扱い）。
**曖昧なまま全体へ適用しない**——「このカードだけ」と言われて全部
変えるのは、言われていないことをするのと同じである。

**Cを採らない理由**: 推定が外れたとき利用者に説明できない。
Forgeは「なぜそう直したか」を言えなければならない。

---

## 5. 軸の拡張計画（CEOの優先順位に対応）

現在2軸。CEOの7分類へ、優先順に対応させる。

| 優先 | CEO分類 | 追加する軸（案） | 依存 |
|---|---|---|---|
| 1 | **情報階層・強調** | `metric_emphasis` / `action_emphasis` / `secondary_visibility` | Design Critic（乱立検出）が既にある |
| 2 | レイアウト・余白・密度 | `screen_density`（既存）/ `list_layout`（card/grid、既にlayoutが在る）/ `grouping` | grouping は新概念 |
| 3 | コンポーネントの見せ方 | `list_surface`（既存）/ `card_style` | |
| 4 | Semantic Color / Theme | `tone`（落ち着いた/温かい/元気）/ `accent_strength` | **IRに`visual_style`が既に在る**が会話から変えられない |
| 5 | タイポグラフィ | `text_scale` / `heading_weight` | Runtime側の対応が要る |
| 6 | 細かな装飾 | `corner_style` / `border_style` | design_tokensが既に在る |
| 7 | アニメーション・遷移 | — | Runtimeに概念が無い。**R5以降** |

### 増やすときの歯止め

`DESIGN-LANGUAGE-V1.md` §6の条件を必ず通す。

* 既存の組み合わせで表現できないか
* Golden App以外にも一般化するか

**軸を増やすほどAIが選び間違える余地とRuntimeが保証すべき組み合わせが
増える。** 1つ足すごとにRuntimeの視覚差テストを1件足す
（TD73: 「1箇所で被せれば全Widgetに効く」は成立しない）。

---

## 6. 色の扱い（CEO判断が要る点）

「赤が強すぎる」に答えるには色を触る必要があるが、
**`#RRGGBB`をAIに書かせてはならない**（R1で潰した方式そのもの）。

### 案: 意味の色に「強度」を持たせる

```
finance.expense       意味      （変えない）
  ↓
emphasis: strong | normal | soft   ← AIが選ぶのはこちら
  ↓
実際の色は ForgeSemanticColors がLight/Darkごとに保証
```

「赤が強すぎる」→ `finance.expense.emphasis = soft`。
意味は変わらず、Runtimeが保証する範囲で弱くなる。

**この案を採るかはCEO判断**（OPEN-DECISIONS.md の判断C）。
「色は触らせない」なら、この行はやらない。

---

## 7. Evidence — TD68の`RevisionRecord`をそのまま使う

TD68で既に設計済みの型に、デザイン用の項目を足す。

```
RevisionRecord（TD68設計済み）
  revision_ref
  base_generation_ref     ← どの生成物への変更か
  sequence                ← 何回目の変更か
  source
  correction_target
  validator_passed
  runtime_outcome
  user_acceptance
  design_language_roles

+ design_revisions: tuple[DesignRevision, ...]   ← 今回追加
      target                 records_list_view
      axis                   list_surface
      before_role            surface.card
      after_role             surface.elevated
      source                 user_correction
```

### 生の発話は持たない（006 §22）

`requested_change` をCEOが挙げていたが、**利用者の言葉そのものは
保存しない**。持つのは

```
complaint_kind : too_strong | too_weak | too_dense | too_cluttered | ...
delta          : emphasis_up | density_down | ...
```

という**閉じた識別子**にする。「赤が強すぎる」という文そのものは残さず、
「強すぎるという不満で、強調を下げた」という事実だけを残す。

これはPrivacy境界であると同時に、**学習素材としても正しい**——
言い回しは無数にあるが、不満の種類は有限だからである。

### 追跡できるようになる対

```
GenerationRecord(ref=7, acceptance=CORRECTED)
   ↑ base_generation_ref
RevisionRecord(ref=1, acceptance=ACCEPTED)
   design_revisions=[ list_surface: card → elevated ]
```

---

## 8. 依存関係と実装順

```
[前提] 016 P0-3（MeasureSemantics消失）を先に直す
        ↓ 意味が保存時に消える状態でRevisionを載せない

Phase R3-1  承認を受ける口をつくる            ← 最小・単独で価値がある
Phase R3-2  RevisionRecord を実装（TD68）
Phase R3-3  Semantic Patch（局所適用）
Phase R3-4  優先1「情報階層・強調」の軸を追加
Phase R3-5  対象特定（AIにidを選ばせる）
Phase R3-6  優先2〜3の軸
Phase R3-7  色（判断Cが「やる」の場合のみ）
Phase R3-8  優先5〜6
[R5以降]    アニメーション・遷移
```

### なぜ R3-1（承認の口）が最初か

**それ単独で閉ループが1本繋がるから。** 「これでいい」を受け取れる
ようになるだけで、既存の`GenerationRecord`が
`ACCEPTED / CORRECTED`で埋まり始める。デザイン修正が1つも実装されて
いなくても価値がある。

いま`note_user_acceptance()`は**実装されているのに呼ぶ口が無い**
——Forgeが4回繰り返した「作ったが呼ばれない」の状態にある。

### R2 Knowledge との関係

**Knowledgeが先にあると精度が上がるが、必須ではない。**

```
Knowledge無し: 軸と選択肢をPromptへ直接書く（今のdesign_intentと同じ）
Knowledge有り: use_when / avoid_when / 代替候補まで渡せる
```

「落ち着いた感じ→relaxed」の判断は`use_when`（日記・ウェルネスなど
落ち着かせたい画面）を知っているほど当たる。**だからKnowledge→
デザイン会話の順を推奨した**が、逆順でも動く。

---

## 9. テスト戦略

### 意味の解釈（AIはTest Double）

| 入力 | 期待 |
|---|---|
| 「残高をもっと目立たせて」 | 残高Widgetの強調が上がる。**他のWidgetは変わらない** |
| 「このカードだけ目立たせて」 | 対象1つだけ変わる |
| 「追加ボタンが目立ちすぎる」 | primary → secondary |
| 対象が曖昧 | **聞き返す**（勝手に全体へ適用しない） |
| 存在しないidをAIが返す | 不採用。UNCLEARへ倒す |

### 局所性（この機能の生命線）

* 変更対象**以外**のWidgetがbyte単位で同一であること
* 残高のKPIが消えていないこと
* record_schemas・stateが変わっていないこと

**「触っていない場所が変わらない」をテストで固定する。**
これが無いと、全体書き直し方式へ静かに戻る。

### Evidence

* `ACCEPTED`と`CORRECTED`が別々に残る
* 生の発話がRecordに現れない
* 生成の成功率と変更の成功率が**混ざらない**（TD68の要求）

### 配線破壊試験（必須）

| 外すもの | 落ちるべきテスト |
|---|---|
| 局所適用をやめ全体書き直しへ戻す | 局所性テスト |
| 対象特定の検証（存在しないid） | UNCLEARテスト |
| 承認の口 | Evidenceテスト |
| RevisionRecordの記録 | 対（CORRECTED/ACCEPTED）テスト |
| 軸ごとの検証 | 語彙外の値が通る |

### Runtime（Flutter）

軸を1つ足すごとに視覚差テストを1件足す（TD73）。
**ただしTD74**: この作業環境にFlutter SDKが無く、
「壊したら落ちるか」を確認できない。CEO環境での確認が要る。

---

## 10. やらないと決めていること

* **文章 → CSS変更にしない。** 必ず意味の層を通す
* **`#RRGGBB`・px・余白の数値をAIに書かせない**
* **触っていない場所を作り直さない**
* **利用者の発話をEvidenceへ保存しない**
* **曖昧なまま全体へ適用しない**（聞き返す）
* **Validator / Runtime のTruthを弱めない**（Knowledgeも修正も参考資料）
* **Golden AppをTemplate化しない**

---

## 11. CEO判断が要る点（再掲）

| # | 判断 | 影響 |
|---|---|---|
| C | 色をAIに触らせるか | §6をやるかどうか。「触らせない」なら優先4は後退 |
| — | 承認の口（R3-1）を先に単独で入れるか | 入れると閉ループが1本繋がる。デザイン修正無しでも価値がある |
| — | 対象特定をUI（タップして指す）まで作るか | AIに選ばせる方式だけなら、UI変更なしで始められる |

---

## 12. 参照

| 文書 | 関係 |
|---|---|
| `docs/spec/DESIGN-LANGUAGE-V1.md` | 変更先の語彙。§6が「増やす条件」 |
| `docs/spec/METRIC-SEMANTICS-V1.md` | 数値の意味（P0-3で保存されるべきもの） |
| `TECH_DEBT.md` TD68 | `RevisionRecord`の設計（そのまま使う） |
| `TECH_DEBT.md` TD65 | 承認の口が無いこと |
| `TECH_DEBT.md` TD73 / TD74 | Runtime反映の限界と、破壊試験ができないこと |
| `docs/OPEN-DECISIONS.md` | 判断待ちの一覧 |
| `docs/PRODUCT-DIRECTION.md` | **最上位方針（変更不可）** |
