# FORGE-R1 残件クローズ — Design Intent と Hero KPI

**2026-08-17 / branch `claude/forge-master-handoff-k46jns`**
**対象: TD69 の未達2件（014 §17 の R1 完了条件）**

---

## 0. 何をしたか（1行）

**AIがDesign Roleを選ぶようになり、選んだ意味を出す先のWidget
（Hero KPI）ができた。** これでR1の完了条件2件が埋まった。

014の報告では **R1 = NO-GO（部分完了）** と書いた。その理由が
この2件だったので、両方を同じブランチで閉じた。

---

## 1. 未達1: 「AIがまだroleを選んでいない」— 解消

### 何が問題だったか

014でSemantic Vocabulary（33 role）を作り、Schema・Validator・
Compiler・Runtime・Evidenceまで繋いだ。しかし**AIには一度も
聞いていなかった**。出ていたroleは全部Compilerが構造から決めたもので、
「AIは意味を決める。Forgeは品質を保証する」の**AI側が動いていない**。

`knowledge_entries()`という渡すための関数まで作って、**誰も呼んで
いなかった**。これはForgeが4回踏んだ「作ったが本番から呼ばれない」
（TD59 / 007 §10 / 010 Phase B / TD64）の5回目になりかけていた。

### どう直したか

Cognitive Pipelineに `design_intent` 段を追加した。

```
Need（利用者の依頼）
  ↓
Compiler が構造から決める role   … 見出し・一覧・ボタン（従来どおり）
AI が意味から決める role         … 密度・面の持ち上げ（今回追加）
  ↓
Forge が軸ごとに検証 → 通らなければ既定値 + fallback記録
```

### 設計上の判断

**値を聞かない。** `font_size`も色コードも一切聞かない。聞くのは
軸ごとの択一だけである。

```
screen_density → density.compact | density.normal | density.relaxed
list_surface   → surface.card    | surface.elevated
```

**自由記述にしない。** 閉じた選択肢から選ばせる理由は2つ。

1. Runtimeが保証できない値が生成物へ入らない
2. **選ばれなかった候補が分かる** — 後から「このNeedでは relaxed では
   なく compact が受け入れられた」という対比が学習素材になる。
   自由記述だと「他に何がありえたか」が残らない

Local AIにとっても、生成より選択の方がはるかに易しい
（Product Direction §3）。

**AIの答えを信用しない。** `is_valid_choice(axis, role)` で軸ごとに
検証する。**語彙全体に含まれるだけでは通さない** —— `metric.primary`
は正しいroleだが `screen_density` の答えとしては誤りである。

**「AIが選んだ」と「Forgeが既定で埋めた」を混ぜない。** 外れた軸は
`fallback_axes`に残り、Decision Traceにも `ai` / `fallback` として
出る。混ぜると「AIの選択が受け入れられた」という学習素材が嘘になる
（`CLAUDE.md` §3「分からないものを楽観側へ倒さない」）。

**AIを呼べなくても壊れない。** Providerが無い・失敗した・応答が
壊れている——どの場合でも既定値で成立する。Design Languageが入った
せいで生成そのものが不安定になるのは本末転倒である。

### 配線破壊試験（6件、すべて落ちた）

外した配線 → 落ちたテスト。**1つも「外しても通る」が無いこと**を
確認している（過去に置物のテストを2回書いたため）。

| 外したもの | 落ちたテスト数 |
|---|---|
| 1. `pipeline.py` の selector 注入 | 9 |
| 2. orchestrator の `select()` 呼び出し | 9 |
| 3. Compilerへの `design_intent` 引き渡し | 4 |
| 4. Compilerの `list_surface` 適用 | 3 |
| 5. Compilerの `screen_density` 適用 | 2 |
| 6. 軸ごとの検証（何でも通す） | 3 |

テストは `backend/tests/test_design_intent_wiring.py`（13件）。

**backend側に置いた理由**: Design Languageの語彙はbackendにあり、
forge_aiはbackendをimportしない。したがって**forge_ai単体のテストでは
軸が空になり、AIへは何も聞かれない**。そこで何件テストを書いても
「本番でAIが呼ばれているか」は分からない。`app`と`forge_ai`の両方が
importできるのはbackendのテストだけで、それが本番と同じ配線である。

---

## 2. 未達2: 「Hero KPI Widgetが無い」— 解消

### 何が問題だったか

014で `metric.primary`（画面で最も重要な単一のKPI）を語彙へ入れた。
ところが**その役割を持てるWidgetが1つも無かった**。

* `text` … Stateの文字列を出すだけ。集計できない
* `bar_chart` … **複数**の値を並べる。単一の主数値にはならない

つまり語彙に「言えるのに作れない言葉」が入っていた。「今月の残高を
一番目立たせて」と言われても、出す先が無い。

### 014の判断を訂正する

014のTD69にはこう書いた。

> **Widgetを増やすのはR3/R5の範囲**であり、R1（意味の層）でWidgetを
> 足すと「Design Languageの成否」と「Widget追加の成否」が混ざる。
> したがって今回は足さない。

**この判断は誤りだった。** 混ざりようがない——`metric.primary`の
出力先が無いこと自体がR1の未達だったからである。語彙に空手形を
残す方が害が大きい。

### 作ったもの: `metric_view`（Forge Language v1.11）

```json
{
  "type": "metric_view", "id": "records_hero_metric",
  "state_ref": "records", "value_field": "amount",
  "aggregate": "sum", "label": "金額の合計",
  "empty_text": "まだ記録がありません",
  "style_role": "metric.primary"
}
```

`bar_chart` との違いは**グループ化しないこと**である——常に値が1つに
なる。`group_by` を**敢えて受け付けない**: 受け付ければ「グループが
複数あるのに数値は1つ」という表示できない文書が作れてしまう。複数
並べたいなら `bar_chart` が既にある。

### 集計を所有しない

合計・平均・件数の計算は `runtime/forge_aggregate.dart` の純粋関数
`aggregateAll()` が行う。`metric_view` は**2番目の利用者**にすぎない
（最初は `bar_chart`）。TRANSFORMはVIEWとは別の層である、という設計
（SELF-EXTENSION-ARCH-REVIEW-v2 §4）を名ばかりにしないため。

`aggregateRecords()`（グループごと）と別関数にしたのは、
`groupBy: ''` を許すと**返り値の要素数が呼び出し方で変わる**関数に
なるからである。呼び出し側が毎回`.first`を書き、その仮定は型に現れない。

### 0件のときに「0」と書かない

```
aggregateAll(records=[], op=sum) → null   （0ではない）
aggregateAll(records=[], op=count) → 0
```

**「合計0円」と「まだ記録が無い」は違う。** 0を返すと呼び出し側が
その区別を復元できず、「今月は0円使った」という事実でない読み取りを
招く。`count` だけ0を返すのは、「0件である」が正しく数えた結果で
あって欠落ではないからである。

### 順序に意味がある

Hero KPIは**一覧より前**に置く。「今月いくら使ったか」を知りたい人は
一覧を読みたいわけではない。一覧の下に置くと、主KPIは「一覧のおまけの
合計」になる。テストで順序を固定してある。

### 出せるからといって出さない

数値Fieldを持たないEntity（habit / todo / diary）には**何も置かない**。
件数を数えることはできるが、「習慣が3件ある」は画面で一番大きく出す
べき数値ではない。`bar_chart` と同じ「根拠のない集計を発明しない」。

### TD37の再発防止（4箇所を同時に更新）

TD37は「Validator・Runtime・Registryの不一致で4種のWidgetが一度も
描画されなかった」実バグである。今回は次を同じcommitで更新した。

| 層 | ファイル |
|---|---|
| Validator | `backend/app/ai/validators/schema_validator.py` |
| Compiler | `forge_ai/core/ir/forge_language_compiler.py` |
| Runtime（Schema/Registry/Builder） | `frontend/lib/json_ui/…` 4ファイル |
| Capability Registry | `backend/app/ai/runtime/capability.py`（`view.metric`） |

### 配線破壊試験（6件、すべて落ちた）

| 外したもの | 落ちたテスト数 |
|---|---|
| 1. CompilerがHero KPIを出さない | 3 |
| 2. Hero KPIを一覧の後ろへ置く | 1 |
| 3. `style_role` を `metric.primary` から外す | 2 |
| 4. Validatorのv1.11から `metric_view` を外す | 11 |
| 5. `value_field` の型検査を外す | 1 |
| 6. `metric_view` で `group_by` を受け付ける | 1 |

テストは `backend/tests/test_hero_metric.py`（13件）。

---

## 3. 実際の生成結果（本番経路、mock provider）

「家計簿をつけたい」に対する Forge Document の構造。

```
tab_view root_tabs                      density.normal   ← AIが選ぶ軸
  column create_tab
    section_header create_section_header text.headline
    form record_form
      choice_field / text_field / date_field / text_field
  column list_tab
    metric_view  records_hero_metric     metric.primary  ← 今回追加
    record_list_view records_list_view   surface.card    ← AIが選ぶ軸
    bar_chart    records_bar_chart       card.summary
  column edit_tab
    …
```

`version: "1.11"` / Validator `valid: True` / エラー0件。

---

## 4. 検証区分（実測 / Test Double / 未検証）

**正直に分けて書く。**

| 項目 | 区分 |
|---|---|
| backend 1182 passed / 16 skipped | **実測**（このセッションで実行） |
| forge_ai 521 passed | **実測** |
| 生成Documentがv1.11で Validator を通ること | **実測** |
| Design IntentのAI選択が生成物へ届くこと | **Test Double**（provider差し替え） |
| Flutter（`metric_view` の描画・`aggregateAll`） | **実測（CI）**。この環境にFlutter SDKが無く自分では実行できないため、CIのfrontend jobで確認した。`flutter analyze` 0件 / `flutter test` 通過 / `build web` 成功（run 32095320829） |
| 実Cloud APIでのDesign Intent選択 | **未検証**。014の指示どおり実APIを呼んでいない（Gemini枠を消費しない） |

**Flutterのテストは書いたが、この環境では実行していない。** 新規2
ファイル（`v1_11_metric_view_test.dart` / `forge_aggregate_all_test.dart`）
はCIで初めて走った。

### CI 1回目（`27b3597`）: frontend job が落ちた

backend 3ジョブは通り、`flutter analyze` が1件で停止した。

```
error • The type 'ForgeWidgetNode' isn't exhaustively matched by the
switch cases since it doesn't match the pattern
'ForgeMetricViewWidgetNode()'
  • test/features/app_generation/data/datasources/
    mock_generator_renderer_contract_test.dart:52
```

**原因**: `ForgeWidgetNode` の網羅switchが2箇所にある。Runtime本体の
`typeNameOf()` は直したが、テスト側にある**手書きの複製**
`_typeNameOf()` を直していなかった。

**同じ場所で落ちたのは3回目である**（v1.3 / v1.6+v1.7 / 今回）。
コード中のコメントにも過去2回が「実バグ」として記録されていた。
TD71として登録した——「忘れずに更新する設計だから忘れられる」典型で
ある。

なお sealed class の網羅性検査があるため、**黙って壊れることはない**。
壊れたアプリが出荷される種類の失敗ではなく、CIを1往復無駄にする種類の
失敗である。

修正して再push。

### CI 2回目（`bc16fb9`）: 全4 job green

```
backend + forge_ai (Python 3.11)   success
backend + forge_ai (Python 3.12)   success
backend smoke (起動 + CORS)         success
frontend (Flutter)                 success
  flutter analyze     0件
  flutter test        通過（新規21件を含む）
  flutter build web   成功
```

これで `metric_view` は**実際に描画されるところまで確認済み**である
——Validator・Compiler・Schema・Registry・Builderのどれか1つでも欠けて
いれば、`v1_11_metric_view_test.dart` が落ちる。

---

## 5. 新たに増えた負債（TD70）

**Curated生成のAI呼び出しが 0回 → 1回 になった。**

Curatedの価値は「速い・安定・無料」である。Gemini実測枠は
**1日20回/Model**（TD66）なので、1生成あたり1回の追加は無視できない。

それでも入れたのは、Curatedだけ意味の選択から外すと**最もよく使われる
経路でDesign Languageが効かない**からである。家計簿と日記が同じ密度に
なる。

直す案は3つ考えてあるが未着手（軸の答えをキャッシュ / Local AIへ寄せる
/ entity_synthesisと1回にまとめる）。詳細は `TECH_DEBT.md` TD70。

---

## 6. 自己監査（PRODUCT-DIRECTION §8 の7問）

1. **目標を実装都合で縮小していないか** — していない。むしろ014で
   「R3の範囲だから」と先送りしたWidget追加を、誤りと認めて戻した
2. **Curatedを消していないか** — 消していない。ただしAI呼び出しが
   1回増えた（TD70として明示）
3. **AIの出力をそのまま信用していないか** — していない。軸ごとに
   検証し、外れたら既定値へ落として記録する
4. **分からないものを楽観側へ倒していないか** — 倒していない。
   0件のとき合計は`null`（0ではない）、fallbackは`fallback_axes`に残す
5. **本番から呼ばれない仕組みを作っていないか** — 配線破壊試験12件
   （6+6）で、外すとテストが落ちることを確認した
6. **実測と公称を分けているか** — §4に区分表を書いた。Flutterは
   **未検証**と明記している
7. **報告を文書に残したか** — このファイル + `docs/HANDOFF.md` +
   `CHANGELOG.md` + `TECH_DEBT.md`（TD69更新 / TD70新設）+
   `docs/spec/DESIGN-LANGUAGE-V1.md`（§5を実態に合わせて更新）
