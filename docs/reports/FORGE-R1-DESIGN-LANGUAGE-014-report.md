# FORGE-R1-ENTRY-AND-DESIGN-LANGUAGE-014 — 実施報告

2026-08-17 / branch `claude/forge-master-handoff-k46jns`

> **結論: R1 Design Language = NO-GO（部分完了）**
> 完了条件のうち2項目が未達である。根拠は §29。

---

## 1. 監査開始時HEAD

`1c5188062b81b728e4a15744f0597bc2c8e4aa2f`（指定と一致を確認）

## 2. 最終commit SHA

`f53963a7c9828686ebba79508216bccb2ed5e36b`
CI run `32027537995` — **全4 job green**（Flutter の analyze / test /
build web を含む）

## 3. GenerationSource旧仕様の問題

013 はこうしていた。

```python
_SOURCE_BY_RESOLUTION = {"curated": CURATED, "generated": CLOUD_AI}
```

`domain_resolution == "generated"` が言っているのは
**「決定的なCurated生成ではなかった」**だけで、誰が作ったかは
言っていない。これを `CLOUD_AI` と等値にすると2つ壊れる。

1. Local AI が構造を作るようになると、その実績が丸ごと Cloud AI の
   成績になる。**Local Routing へ昇格してよいかの判断根拠が最初から
   汚染される**
2. **現に壊れていた** — Mock Provider の生成が `CLOUD_AI` として
   記録されていた。013 のテスト自身が `assertIn(CLOUD_AI, sources)`
   と書いて、その誤りを固定していた

## 4. 新しいsource判定方法

Registry の `deployment` / `test_only` を Single Source of Truth に
した（`source_for_generated()`）。

```
1. domain_resolution == "curated"  → CURATED
2. test_only                        → TEST_DOUBLE   ← 先に見る
3. deployment == LOCAL              → LOCAL_AI
4. deployment == CLOUD              → CLOUD_AI
5. 未登録 / provider不明             → UNKNOWN
```

**順序に意味がある。** `mock` は Registry 上 `deployment=local` なので、
`test_only` を後に見ると Mock が Local AI の実績を水増しする。

Curated を先に見るのは、Curated 経路では生成 stage が AI を呼ばない
のに、会話ステップの Provider が `last_provider_used` に残りうる
ためである。**生成が AI を呼んでいないのに、会話の Provider で由来を
決めてはならない。**

やらないこと: `ai_calls > 0` だから Cloud という推測、Model 名の文字列
からの local/cloud 判定、UNKNOWN を楽観値にすること。

## 5. mockはどう扱うか

`GenerationSource.TEST_DOUBLE` を新設した。**Cloud にも Local にも
入れない。** どちらへ入れても、その側の統計が嘘になる。

`TEST_DOUBLE.is_usable_for_training` は `False`（Mock の出力を教師に
すると Mock の癖を学ぶ）。

## 6. Local AIがLOCAL_AIとして記録される証拠

実モデルは呼んでいない（環境に無い、TD51）。**契約を Registry の
宣言で固定した。**

```
test_a_local_provider_is_recorded_as_local_ai
    _generation_source(trace, "local") is GenerationSource.LOCAL_AI

test_the_registry_is_the_single_source_of_truth
    全 Provider について deployment/test_only から期待値を導出し照合
```

後者が要点である。Provider を1つ増やすたびに判定表へ書き足す形では
ないので、**Provider 追加時に由来判定を書き忘れることができない**。

## 7. generation_refのProduction Path

```
GenerationEvidenceStore.record() → ref
  ↓ _record_generation() が返す（013 は捨てていた）
PipelineRunResult.generation_ref
  ↓
（未接続）Runtime Evidence / User Acceptance
```

`ConversationSession` へ持たせる案は**撤回した**。BUILD 後に
`default_conversation_store.discard()` するので、置いても必ず捨て
られる。「あるが誰も使えない」を増やさない（`CLAUDE.md` §3）。

**HTTP レスポンスへは出していない**（§3 が許容）。

## 8. Runtime/User feedbackを後から書けるか

**書ける。テストで確認済み。**

```
test_the_ref_can_actually_be_used_to_write_feedback_later
    note_runtime_outcome([ref], RENDERED)  → 1件書けた
    note_user_acceptance([ref], ACCEPTED)  → 1件書けた
    → is_positive_example == True
```

`UNKNOWN` を勝手に `RENDERED` / `ACCEPTED` にはしていない。
**書ける構造だけ先に作った**（§4）。

## 9. Update/Revision Evidenceの設計判断

**案A（`GenerationRecord` + `RevisionRecord`、関係で繋ぐ）を採用。**
実装は R2（TD68）。

* **案B（1つの型に `operation` を持たせる）を採らない理由**:
  `validator_passed` の意味が operation ごとに変わる。集計のたびに
  割る必要があり、割り忘れると静かに混ざる。013 で `/update` を
  除外した理由が、型の中へ戻ってくる
* **案C（専用の別モデル）を採らない理由**: `AcceptanceSignal` /
  `RuntimeOutcome` など共有すべき語彙が多い。別系統にすると同じ概念が
  2つの名前を持ち、突き合わせられない

最小契約は TD68 に記載（`base_generation_ref` で関係を持ち、
生のユーザー発話は持たない）。

**「今回は除外」で終わらせていない。**

## 10. Identifier境界

`[a-z][a-z0-9]*([._-][a-z0-9]+)*`、64文字以内。

通す: `metric.primary` `finance.income` `surface.elevated`
弾く: `残高を目立たせてほしい` `metric primary` `Metric.Primary` 空 非文字列

大文字を弾くのは、`metric.primary` と `Metric.Primary` が両方記録
されると **Evidence の集計が割れる**ためである。

目的は綺麗さではなく、**利用者の発話が Evidence へ混入する経路を
塞ぐこと**（006 §22）。エラー文も入力を丸ごと出さない。

## 11. Semantic Vocabulary一覧

**33 role。** 全文は `docs/spec/DESIGN-LANGUAGE-V1.md`。

| 種別 | role |
|---|---|
| typography | text.display / headline / title / body / label / secondary、metric.primary / secondary |
| color | color.primary / secondary、state.success / warning / danger、finance.income / expense、text.primary |
| surface | surface.background / card / elevated / selected |
| shape | shape.small / medium / large / pill |
| density | density.compact / normal / relaxed |
| component | button.primary / secondary、card.metric / summary / list、navigation.primary |

各 role は `meaning` / `use_when` / `avoid_when` を持つ。
**誤用を止める情報**が要る——`metric.primary` を全数値へ付けると
階層が消える。

## 12〜17. 各層の変更

| 層 | 変更 |
|---|---|
| **Schema** | v1.10 追加。`style_role` は全 Widget 共通の任意キー。**Widget は1つも増やしていない** |
| **Compiler** | 構造から決まる role を出力（section_header→text.headline、record_list_view→card.list、bar_chart→card.summary、button→button.primary/secondary）。version を 1.10 へ |
| **Validator** | `_check_widget_schema` 冒頭の**1箇所**で検査。語彙外は `unknown_style_role`、v1.10 未満は `field_not_allowed_in_version` |
| **Runtime** | `design_language.dart`。`_build()` の**1箇所**で被せる。色は Theme から引き、固定色を書かない |
| **Conversation** | **未変更**（TD69。§28 参照） |
| **Generation Evidence** | 最終 Document の事実から抽出。決定的・重複を潰す・語彙外は捨てる |

Schema と Runtime を「1箇所」にしたのは同じ理由である。type 別の
`allowed_keys` や 19 個の builder へ配ると、**Widget を1つ足すたびに
書き忘れる**（`CLAUDE.md` §3）。

## 18. Golden Finance E2E

**完全には成立していない。** 正直に書く。

成立した部分:

```
"家計の支出をカテゴリ別に管理したい"
  → Compiler が style_role を出力
  → Validator PASS（version 1.10）
  → GenerationRecord.design_language_roles =
       ("button.secondary", "card.list", "card.summary", "text.headline")
```

**成立しなかった部分**: `metric.primary` / `finance.income` /
`finance.expense` を含む Document を、Production Path が生成できない。
**単一の重要な数値を表示する Widget が存在しない**ためである。

現在の集計手段は `bar_chart` の `group_by` / `aggregate` だけで、
これは複数値の内訳であり単一 KPI ではない。

Widget を足すのは R3/R5 の範囲であり、R1（意味の層）で足すと
「Design Language の成否」と「Widget 追加の成否」が混ざる。
したがって**今回は足さなかった**（TD69）。

## 19〜23. 検証

| 対象 | 結果 |
|---|---|
| backend tests | **1155 passed / 16 skipped** |
| forge_ai tests | **521 passed** |
| Flutter test | CI success（件数は job API から読めないため数字は据え置き） |
| flutter analyze | CI success（`--fatal-infos --fatal-warnings`） |
| flutter build web | CI success |
| CI 全 job | **4/4 green**（run `32027537995`） |

014 で追加したテスト: `test_design_language.py`（30件）、
`test_generation_evidence.py` を新契約へ書き直し（+7件）。

## 24. intentionally broken regression

**4パターンすべてで対応するテストが落ちた**（戻すと通る）。

| # | 壊した配線 | 落ちた件数 |
|---|---|---|
| A | `test_only` を先に見るのをやめる（mock→LOCAL_AI） | 3 |
| B | `generation_ref` の引継ぎを消す | 2 |
| C | Compiler から role 生成を外す | 1 |
| E | Evidence の role 抽出を外す | 1 |

（D の Runtime style mapping は Flutter 側で、この環境に Flutter が
無いため未実施。CI の analyze/test/build は通っている。）

## 25. 未接続箇所

1. **Conversation へ語彙を渡していない** — `knowledge_entries()` は
   用意したが prompt へ渡していない。**AI はまだ role を選んでいない**
2. **Hero KPI Widget が無い** — `metric.primary` の出力先が無い
3. **Runtime / User Acceptance** — Flutter から結果が戻る経路と、
   生成物への承認 UI が無い
4. **Flutter 側の role 単体テスト** — CI の既存テストは通るが、
   `design_language.dart` 専用のテストは書いていない

## 26. Technical Debt

TD68（Update/Revision Evidence、設計のみ）、TD69（R1 未達分）を新規に
記録。既存の TD41 / TD51 / TD60 / TD64〜67 は継続。

## 27. Local AI改善へどう繋がるか

**Evidence の粒度が「値」から「意味」へ上がった。**

```
013まで: この生成物は Validator を通った
014から: この Need に対して text.headline / card.list / card.summary
         を選び、Validator を通った
```

後者は Local AI の教師データになりうる。前者はならない。
`GenerationRecord.design_language_roles` に実際に残ることを、
HTTP API を叩くだけのテストで確認している。

ただし **AI がまだ role を選んでいない**ので、現時点で貯まるのは
「Compiler が構造から決めた role」である。これは Local AI の
**出力目標**としては使えるが、**AI の判断の良し悪し**は測れない。

## 28. 完成画像との距離が何によって縮まったか

**正直に言うと、見た目はまだほとんど変わっていない。**

縮まったのは「見た目を良くするための足場」である。

* 値のブレが構造的に消える形になった（role → Runtime が保証）
* 階層（display > headline > title > body > secondary）が語彙として
  定義された
* `finance.income` と `state.success` を**別の色**にした——支出が
  エラーのように見えない

縮まっていないのは、**完成画像の核心である Hero KPI** である。
「今月の残高を一番目立たせる」が、まだ構造として作れない。

## 29. R2へ進めるか — **NO-GO（R1 は部分完了）**

014 §17 の完了条件に対して:

| 条件 | 状態 |
|---|---|
| Generated を無条件 CLOUD_AI 扱いしない | ✅ |
| Local 生成が LOCAL_AI になる契約 | ✅ |
| mock が Cloud 実績へ混ざらない | ✅ |
| generation_ref が Production Path へ流れる | ✅ |
| Generation feedback を後から書ける構造 | ✅ |
| Update Evidence の将来設計を正式記録 | ✅ TD68 |
| Semantic Identifier 境界 | ✅ |
| Design Language V1 | ✅ 33 role |
| Schema / Compiler / Validator / Runtime 接続 | ✅ |
| **Conversation 接続** | ❌ **未達** |
| GenerationRecord.design_language_roles 接続 | ✅ |
| **Finance Golden E2E** | ❌ **未達**（Hero KPI Widget が無い） |
| 全 test green / web build / CI | ✅ |
| report / HANDOFF / push | ✅ |

**2つ未達なので GO とは言えない。**

とくに Conversation 未接続は重い——「AI は意味を決める」の**AI 側が
まだ動いていない**。今 role を出しているのは Compiler であり、
Design Language が本来狙った「AI が語彙から選ぶ」は成立していない。

### R1 を GO にするために必要なこと（次にやる）

1. Conversation / Cognitive Pipeline へ `knowledge_entries()` を渡し、
   AI が role を選べるようにする
2. Hero KPI Widget（単一の重要な数値）を追加し、`metric.primary` /
   `finance.income` / `finance.expense` を Production Path で出せる
   ようにする
3. その上で Finance Golden E2E を一本通す

1 は R1 の核心なので**先にやる**。2 は Widget 追加なので R3 の前倒し
になるが、Golden E2E の完了条件がそれを要求している。

---

## 30. Product Direction 自己監査（§18、10問）

| # | 問い | 答え |
|---|---|---|
| 1 | 見た目は実際に良くなったか | **まだほとんど変わっていない。** 良くするための足場（語彙・階層・保証）ができた段階（§28） |
| 2 | Local AI が選べる Vocabulary か | **なっている。** 33 role が `meaning`/`use_when`/`avoid_when` つきで、`knowledge_entries()` で渡せる。ただし**まだ渡していない** |
| 3 | Local AI の実績を Cloud として誤記録していないか | **していない。** それが §2 の修正そのもの。Registry の事実から決め、mock は TEST_DOUBLE |
| 4 | Evidence が Production から本当に残るか | **残る。** HTTP API を叩くだけのテストで確認。配線を外すと落ちる |
| 5 | 後から Runtime/User Feedback を紐付けられるか | **できる。** `generation_ref` が Pipeline 結果まで届き、書けることをテストで確認 |
| 6 | Golden App を Template 化していないか | **していない。** Curated は触っていない。role は構造から決めており、Domain 別の分岐を1つも足していない |
| 7 | Raw Style 依存へ逆戻りしていないか | **していない。** `style_role` は意味だけ。px も色も Runtime 側にある |
| 8 | 実装都合で最終目標を縮小していないか | **していない。** Conversation 未接続と Hero KPI 欠如を、GO を出さない理由として正面から書いた |
| 9 | 「存在するが誰も呼ばない」部品を増やしていないか | **1つ作りかけて撤回した** — `ConversationSession.last_generation_ref` は BUILD 後に必ず捨てられるので消した。`knowledge_entries()` は**現時点で誰も呼んでいない**（TD69 に明記） |
| 10 | 完成画像と Local AI の2軸を同時に前進させたか | **半分。** Local AI 側（Evidence の粒度が意味単位になった）は前進。完成画像側は足場のみで、見た目そのものは動いていない |

### §18-9 について補足

`knowledge_entries()` は「存在するが誰も呼ばない」状態である。
これを許容した理由は、**呼ぶ相手（Conversation prompt）が次の作業で
必ず来る**ことと、TD69 に名指しで残したことである。
次の作業で繋がらなければ、これは5回目の同じ失敗になる。
