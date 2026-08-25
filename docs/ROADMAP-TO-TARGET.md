# 完成図までのロードマップ（閉ループ版）

2026-08-14 / 起点: CEO提示の完成図（AI-NATIVE APP BUILDER）
**上位文書**: `docs/PRODUCT-DIRECTION.md`（変更不可）

> **2026-08-24 追記 — AI/Learning領域の正式Architectureができた。**
>
> このロードマップが「Knowledge → Retrieval → Experience → Benchmark
> へ順次接続する」と書いていた部分は、
> **`docs/architecture/FORGE-GROWING-AI-ARCHITECTURE.md`** が
> 正式なArchitectureとして引き受ける（FORGE-017）。
>
> 位置付けは `PRODUCT-DIRECTION`（最上位）→ Growing AI Architecture
> （AI/Learning領域）→ このロードマップ（段取り）。矛盾したら上が勝つ。
>
> 直近の実装順は次に固定された（017 §24）。
>
> | | 内容 | 状態 |
> |---|---|---|
> | A | MeasureSemantics消失修正 | ✅ `50b2c3d` |
> | B | Feedback / Revision Foundation | ✅ `fe2664c` |
> | A1 | Revision training provenance | ✅ `b61b36d`（017A §1） |
> | A2 | Feedback Event + ID分離 | ✅ `d163e6f`（017A §2-§4） |
> | A3 | Learning Contract + Local Promotion Gate | ✅ `2db1fcd`（017A §5-§7,§10） |
> | C | 残R1 Hardening | ✅ `a514a37`（017A §14） |
> | D | R2 Forge Knowledge / RAG | ✅ `e40c861`（017A §8,§15） |
> | E | Growing AI Learning Event Foundation | ✅ `6abc3a8` |
> | E-A | Learning Boundary Hardening + Agent Protocol | ✅ FORGE-018A |
> | F | Semantic Design Revision | ⬜ |
>
> **Dで`scope`と`app_id`は型に入った**（`KnowledgeEntry`）。
> `app_id`は017 Review時点でコードに0件だったので、これが最初の1箇所。

---

## 0. 前版（同日）の撤回

**このファイルの初版は Product Direction に違反していた。** 撤回して
書き直す。何を間違えたかを残しておく。

初版は次の順序を提案していた:

```
P0 見た目の言語 → P1〜P4 Widget追加 → P5 Web IDE → P6 公開/API
```

**Local AI がどこにも無い。** これは Product Direction §6 が明示的に
禁止している「まずUIを完成させてからLocal AI」そのものである。

さらに §2「Visual Quality改善とLocal AI改善は別々のロードマップでは
ない」に対しても、初版は Visual だけの一本道になっていた。

**なぜ間違えたか**（同じ形を繰り返さないために書く）: 完成図が
**見た目の絵**だったので、見たものをそのまま作業計画へ写した。
完成図は「Forgeが満たすべき品質基準」(§1) であって、絵の模写指示では
ない。絵に写っていないもの——**その品質を Forge 自身が獲得していく
仕組み**——が抜けた。

以下は、Product Direction §2 の閉ループを**1周ずつ閉じる**形へ
組み直したものである。

---

## 1. 設計の中心 — Design Language は Local AI のための語彙である

Product Direction §3 が、このロードマップ全体の形を決めている。

```
AIは意味を決める。Forgeは品質を保証する。
```

したがって Design Token は「色の一覧」ではなく **AIが選ぶ語彙** として
設計する。

```
❌ AIが決める:  font-size 36px / #23D18B / padding 16
✅ AIが決める:  metric.primary / finance.income / surface.elevated
   Forgeが保証: それが実際に何pxで何色になるか
```

この形にすると3つが同時に成り立つ。

1. **生成品質**が上がる（値のブレが構造的に消える）
2. **Local AI が小さくて済む**（語彙選択は値生成よりはるかに易しい）
3. **Evidence が意味単位で残る**（「#23D18Bが選ばれた」ではなく
   「finance.income が選ばれ、ユーザーが ACCEPTED した」）

3番目が閉ループの入口である。**見た目の作業が、そのまま Local AI の
学習素材になる。** これが「分離しない」の実装上の意味である。

---

## 2. 現状の底（実測、2026-08-14）

推測ではなく実コードで確認した値。

```
Widget          19種（v1.9）
design_tokens   color_scheme（role→#RRGGBB の自由map）/ corner_radius
                / spacing_scale の3キーのみ
                → 意味の色・タイポ・影・グラデーション・ダークモード無し
グラフ          bar_chart のみ
画像/カレンダー  無し
アイコン        無し

Compiler が group_by/aggregate を出力する箇所   0件
ExperienceStore を Production から呼ぶ箇所      0件
Knowledge / RAG                                 未着手
Local AI 実モデル実行                            0回（環境制約 TD51）
```

**閉ループのうち、実際に閉じている辺は1本も無い。**

---

## 3. 完成図の分解（品質基準として）

完成図は模写対象ではなく**基準**なので、「何を選べれば描けるか」で
分解する。

### 3-1. 既存19 Widgetで今日でも描けるもの

大きな数値・前月比・チェック行・セクション見出し・タブ切替。
**骨格の相当部分は既に描ける。** 届いていないのは装飾と情報密度。

### 3-2. 新しい Widget が要るもの

| 要素 | 追加 | 大きさ |
|---|---|---|
| ドーナツ/リング | `donut_chart` | 中 |
| 行内の進捗バー | `progress_bar` | 小 |
| アイコン・絵文字 | `icon` | 小 |
| 下部ナビ | `bottom_navigation` | 中 |
| ＋ボタン | `fab` | 小 |
| ヒーロー画像 | `image` + `data.image` | 大 |
| カレンダー | `calendar` + `view.calendar` | 大 |
| 行の左右装飾 | `list`/`record_list_view` 拡張 | 中 |

**Template化しないこと**(§4): これらは「家計簿を作るための部品」では
なく、**未知のアプリでも組み合わせられる語彙**として設計する。
Golden App が描けるかは評価であって、目標ではない。

### 3-3. Design Language（Widget追加ゼロ）

意味の色（`finance.income` / `metric.primary` / `state.positive`）、
`surface.*`、`text.*`、typography scale、elevation、gradient、
color_mode。

---

## 4. Phase — 各Phaseで閉ループを1周させる

**すべてのPhaseが「品質」と「Local AIの素材」の両方を出す。**
どちらか片方だけのPhaseは作らない。

### R0. Evidence を Production から記録する（**最優先・Widget追加0**）

Product Direction §7 が名指しした違反を先に消す。

* `ExperienceStore` を `/converse`・`/generate`・`/update` から**実際に
  呼ぶ**（現在0件）
* 記録する Evidence:
  Validator結果 / Runtime成否 / 構造化出力の妥当性 / repair回数 /
  fallbackの有無 / **User ACCEPTED・CORRECTED**（011 §5で分離済み）
* `ExperienceRecord` は本文を持てない型なので、配線しても利用者の
  入力は入らない（006 §22の担保は維持）

**閉じる辺**: `Rendered Application → User Acceptance / Correction →
Experience`

> **2026-08-17 実施済み。** 実施中に、この辺が**一部塞がっている**ことが
> 分かった——Curated Domainの**生成stage**はAI Providerを呼ばないので、
> R0の記録(AI呼び出し単位)には生成物の事実が残らなかった(TD65)。
>
> **013で解決済み。** AI呼び出しの記録とは別に`GenerationRecord`
> (生成物単位)を持ち、`source=curated`として残すようにした。
> Curatedを消さず、AIを無理に通さずに、閉ループへ載せている。
>
> なお初出時に「Curated経路からExperienceが1件も出ない」と書いたのは
> **測った範囲より広い主張**だった。会話(`/converse`)は`ConversationEngine`
> 自身がAIを呼ぶので、会話ステップのExperienceは残る。

**なぜ最初か**: これが無いと、以降のどのPhaseも「良くなったか」を
測れない。Design Token を入れても、それが受け入れられたのか
訂正されたのかが残らない。**測れないまま作ると、Local AIへ渡す
素材が1つも増えない。**

### R1. Design Language を「AIが選ぶ語彙」として導入 ✅ 完了(2026-08-17)

> **状態: GO**（`FORGE-R1-CLOSURE-015`、CIのFlutter jobが緑であることを条件）
> 詳細: `docs/reports/FORGE-R1-CLOSURE-015-report.md`
>
> 3回に分けて閉じた。014で語彙とSchema、TD69でAI選択とHero KPI、
> 015で「意味が本当に画面とEvidenceへ届いているか」。
>
> **015で直した主な穴**（すべて再現してから直した）:
> * 数値だからという理由でKPIを発明していた（評価の合計・魚の長さの合計）
> * `metric.primary`を付けても**実際には描画が変わっていなかった**
> * `button.primary`/`secondary`が画面上で区別できなかった
> * AIが選んだroleとForgeの既定値が**Evidence上で混ざっていた**
> * forge_aiがbackendを遅延importし、環境で挙動が変わっていた
> * 単純な金額合計を「残高」と呼びかねない状態だった
>
> **残った負債**: TD70（CuratedのAI呼び出し1回、推奨解を記録済み）、
> TD73（roleの反映はWidgetごとの対応が要る）。

* `design_tokens` を意味的役割へ拡張（§1の形）
* **Schema + Compiler + Validator + Runtime + Conversation** まで通す
  （Definition of Done）。Runtimeだけ実装して終わらせない
* Cognitive Pipeline が**役割を選ぶ**ようにする（値は選ばせない）
* Design Critic に「役割が選ばれているか」の軸を追加
* R0で入れた Evidence に**どの役割が選ばれ、受け入れられたか**が残る

**閉じる辺**: `Capability/Design Language → Forge Language → Validator
→ Runtime → Visual Quality Evidence` ✅ 全辺が繋がった

> ただし最後の辺の名前は **Visual *Structure* Evidence** にした。
> 主KPI数・被覆率・階層深さのような**決定的に測れる構造の事実**であって、
> 「美しさ」は測れていない。測れていないものを測ったことにしない。

**生成品質**: 完成図の「洗練された感じ」の相当部分。
**Local AI素材**: 語彙選択の正解/不正解データが貯まり始める
（**AIが選んだものとForgeの既定値を型で分けてある**ので、既定値を
成功例として学習することが無い）。

### R2. Forge Knowledge / RAG（Local AI優先順位 #1）

Product Direction §6 の優先1位。R1で語彙が固まった部分から着手する。

* Forge Language / Capability / Design Language の**Forge固有知識**を
  検索可能な形で持つ
* Cloud AI にも Local AI にも**同じ Knowledge を参照させる**
* 「Knowledgeはあるが Local AI が参照しない」を作らない(§7)

**閉じる辺**: `Knowledge → RAG → Forge AI / Local AI`

**なぜ R1 の後か**: 仕様が動いている最中の知識を固めると、古い仕様を
配ることになる（§6の後段の警告）。R1で語彙が安定した範囲だけを
Knowledge へ入れる。

### R2.5. Curated Domain を学習ループへ載せる(**013で実施済み**)

TD65として記録した、R0で見つかった構造上の問題。

* Curated Domainの**生成stage**はAI Providerを呼ばない(実測0.01秒)
* 速く・安定し・Quota消費0・品質も一定なので、単純に消すのは後退である
* 一方で Product Direction §4「有限Template選択システムへの退化は禁止」に
  触れる形に見える
* **Local AIへの影響が大きい** ——生成物についてのEvidenceが残らなかった

当初は3択(叩き台化 / 位置付け直し / R1で見直し)を挙げてCEO判断待ちに
していたが、**013で第4の案を採って実装した**。

> **AI呼び出しの記録**と、**生成物の記録**を分ける。
> `GenerationRecord.source`が由来(`curated` / `cloud_ai` / `local_ai` /
> `composition`)を持つので、AIを呼ばずに作った成功例も同じ形の
> Evidenceとして並ぶ。

Curatedを消さず、AIを無理に通さず、閉ループへ載せられる。
**残っているのは「Curatedを叩き台にAIが調整する」(旧案1)を実際に
やるかどうか**で、これはR1でDesign Languageの語彙が入ってからの方が
判断しやすい(調整すべき軸が語彙として存在しないと、何を調整するのか
決められない)。

### R3. 小さい Widget 4つ + Compiler接続

`progress_bar` / `icon` / `fab` / 絵文字選択。

* **Widget追加と Compiler接続を必ず対にする**(§7)
* R1のTokenの上に載るので、追加した瞬間から馴染む
* `transform.aggregate` の Compiler接続もここで済ませる
  （Runtime実装済みのまま会話から到達しない状態を解消）

**閉じる辺**: `Capability → Forge Language → Compiler → Runtime`

### R4. Shadow Evaluation（Local AI優先順位 #3）

* 本番の応答は現行Providerのまま、裏で候補Modelにも同じTaskを解かせる
* 比較の判定は **Cloudの出力ではなく** Validator / Runtime成否 /
  構造化出力妥当性 / Held-out benchmark で行う(§5)
* `ShadowPlan` は実装済み（有効化されていないだけ）

**閉じる辺**: `Local AI → ... → Benchmark`（評価の輪）

### R5. ドーナツ + 下部ナビ + 行拡張

完成図の見た目に最も効く部分。R1〜R3が済んでいれば追加は素直。

### R6. Curated Dataset → LoRA/Adapter → Promotion（優先順位 #4〜#6）

* R0で貯めた Evidence から、**ACCEPTED と Validator合格が揃ったもの**
  だけを Dataset 候補にする
* **Cloudの回答をそのまま模倣させない**(§5)
* Benchmark で Task単位に Local Routing へ昇格（配線は011 §J で済み、
  データ待ち）

### R7. 画像・カレンダー / Web IDE / 公開

重い順に最後。**Web IDE は器の変更**であり、生成物の質(軸A)が
上がってから着手する。

---

## 5. 「コンポーネント128」を目標にしない

完成図フッターの数字を目標として扱わないことを提案する。

完成図の3画面は**10種前後の追加**で描ける。128はWidget種類ではなく
配置数を数えている可能性が高い。種類を増やすほど Compiler・Validator・
Runtime の三者を揃える負担が増える（TD37で実際に踏んだ）。

数字が目標になると「128種あるが会話からは使えない」が正当化され、
Definition of Done §7 の禁止事項そのものになる。

---

## 6. このロードマップの検証区分（§39）

* **実測**: Widget 19種 / `design_tokens` 3キー / Compilerが
  `group_by` を出さないこと / `ExperienceStore` の Production 呼び出し
  0件 — いずれも実コードで確認済み(呼び出し0件は**2026-08-17のR0で解消**)
* **実測(2026-08-17追加)**: Curated Domainの**生成stage**はAI呼び出し
  0件(TD65) / 観測した1 Modelについて`quotaValue=20`、`quotaId`は
  `PerProjectPerModel`(TD66。合計値と鍵単位かProject単位かは**未検証**)
* **設計判断**: Phase の順序と粒度 — 着手すると変わりうる
* **未検証**: 完成図の3画面が R1〜R5 で実際に描けるかは、**描いてみる
  まで分からない**。R1完了時点で1画面を手で組んで確かめ、差分をここへ
  反映する

---

## 7. 2026-08-25 FORGE-018更新 — Learning Event Foundation

R2 Knowledgeの次の閉ループ辺として、既存Evidenceから単一Projectorを経て
Local Learning Event、Consent/Sanitization、Cloud Export判定、Dataset
Candidate lineageまでProduction接続した。AI_CALL / GENERATION / FEEDBACKは
HTTP実経路でemit済み。RevisionはFORGE-019、BUILD/COMPILE/TEST/RUNTIME等は
契約のみで未emit。

Cloud送信はAuth/RLS/server-issued identityが無いため既定OFF。Local Eventと
拒否理由付きlineageは残るが、送信済みとは扱わない。次はFORGE-019でSemantic
Design RevisionとFlutter host feedbackを同じ閉ループへ繋ぐ。

## 8. 2026-08-25 FORGE-018A更新 — Boundary Hardening

FORGE-019前のBlocking Reviewを閉じた。Cloud収集とDataset/Weight Trainingの
権限を分離し、Event provenanceをModel training provenanceから別型にした。
Local Event生成はsubject Consentに依存せず、Cloud境界でrequest-scopedな
Consent/App Identityを明示評価する。Rejected評価はEvaluation Recordへ残し、
Dataset Candidateは本当にTraining eligibleなEventだけになった。

次はFORGE-019 Semantic Design Revision。ただしCloud送信、durable outbox、
Supabase Auth/RLS/server identityは未実装のままであり、FORGE-019がそれらを
実装済みと仮定してはならない。
