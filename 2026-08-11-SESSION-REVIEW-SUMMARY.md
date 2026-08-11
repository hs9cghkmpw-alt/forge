# 2026-08-11 作業まとめ(レビュー用)

**対象ブランチ:** `claude/forge-master-handoff-k46jns`
**このファイルの目的:** 今回のセッション(`FORGE-AI-QUALITY-001`)で
Claudeが実際に行ったことを、CEOがレビューしやすいように1箇所へ
まとめたもの。詳細は各章末にリンクした`TECH_DEBT.md`の該当TD項目を参照。

**きっかけ:** CEOからの「生成できるアプリのクオリティを最大限にしたい」
という依頼に対し、4つの方向性を提示して`AskUserQuestion`で確認したところ、
CEOは4つすべて(色々なジャンルで実際に生成→不具合修正/primary_concept
選定の見直し/Design Critic評価範囲拡大/Widget・Template種類拡充)を選択。
すべてに着手した。

---

## 0. 進め方(前回までと同じ方針)

1. 実際に`uvicorn`を起動し、実際のGemini APIへ日本語プロンプトを何件も
   投げて、生成された中身を1件ずつ目視確認する(推測ではなく実機確認)。
2. 見つかった不具合ごとに、根本原因を特定→最小限の修正→
   forge_ai/backend全テストスイート(実行のたび件数が増加、最終959件)を
   都度実行して回帰が無いことを確認→再度実機確認、の順で進めた。
3. 修正のたびに`TECH_DEBT.md`へ新しいTD番号(TD26〜TD29)を追記し、
   「今回わかったこと」「直したこと」「まだ直っていないこと」を正直に
   記録した。

---

## 1. TD26: アンケート・スケジュール等の初期データが、依頼内容と無関係に
いつも同じ画一的な値になっていた

**発見**: 「満足度アンケートを作って」を実行すると、内容に関わらず
常に`['最初の質問']`が返ってきた。「週間スケジュール」も常に
`['定例ミーティング']`。

**原因**: `forge_ai/core/compiler.py`の`Compiler.compile()`が、Gemini
(Provider)の応答から`title`しか読み取っておらず、初期データは
「先頭の概念名→固定の例値」という静的な決め打ちテーブルのみに依存
していた。このテーブルは依頼内容の違いを一切反映できない。

**修正**: PromptへGeminiへの指示を追加し、依頼内容に即した
`example_items`(具体的な初期データ例)を返してもらい、それを静的
テーブルより優先するようにした。既存のMock環境・テストには影響しない
(Geminiだけがこの新しいフィールドを返す)。

**実機確認結果(修正前→後)**:
| プロンプト | 修正前 | 修正後 |
|---|---|---|
| 満足度アンケート | `['最初の質問']` | `['サービス全体の満足度を教えてください', ...]`(実際の質問文3件) |
| 週間スケジュール | `['定例ミーティング']` | `['月曜 10:00 - チーム定例ミーティング', ...]`(実際の予定3件) |

→ 詳細: `TECH_DEBT.md` TD26

---

## 2. TD27: 「通院記録」「勤怠」が、誤って汎用日記アプリになっていた

**発見**: 「通院記録を管理するアプリを作って」「勤怠を記録するアプリを
作って」が、どちらも`diary`(日記)Domainへ分類され、診療記録・勤務
記録として意味のあるフィールドではなく、汎用的な日記フィールド
(タイトル/本文/気分/日付)が生成されていた。

**原因**: 語彙辞書(`lexicon.py`)に「通院」「勤怠」の登録が無く、
「記録」という汎用動詞だけがdiaryのActionと一致してしまい、
本来のhospital/attendance Domainへ全く点数が入っていなかった。

**修正**: 「通院」→appointment、「勤怠」→statusという2語を辞書へ
追加。「毎日」「写真」のような汎用語と違い、他文脈でまず使われない
語であるため、追加による副作用のリスクは低いと判断した。

**修正後の挙動**: 「通院記録」はhospital Domainへ正しく分類され、
医療情報を扱うことへの同意確認(既存のPrivacy確認フロー)へ合流する
ようになった。「勤怠」はattendance Domainへ正しく分類され、
「Attendanceなのか Task Managementなのか」を尋ねる確認フローへ合流
するようになった(いずれも、無確認で誤った汎用アプリを作ってしまう
よりずっと安全)。

→ 詳細: `TECH_DEBT.md` TD27

---

## 3. 「主役となる概念」の選び方を、travel限定の応急処置から
汎用的な仕組みへ

**背景**: 前回セッション(TD24)で、「旅行の持ち物チェックリストを
作って」が「京都旅行」等の旅行先を生成してしまう不具合を、
`_PREFER_AS_PRIMARY_WHEN_MENTIONED = ("belongings",)`という、
travel Domain 1件だけを想定した名前の直書きリストで応急処置していた。

**今回やったこと**: 全15 Domainの概念定義を実際に1つずつ確認した
結果、この問題(先頭概念がDomain判定のトリガーなだけで、実際に
言及したい対象ではない)を持つのはtravelの`"destination"`のみだと
確認できた。そこで、`DomainConcept`へ`primary_candidate: bool = True`
という汎用的なフラグを追加し、travel専用の直書きリストを廃止した。
将来別のDomainで同じ問題が見つかった場合、Domain定義側にフラグを
立てるだけで対応でき、`application_planner.py`本体を変更する必要が
なくなった。

**あえてやらなかったこと**: 「言及された概念を無条件に優先する」という
もっと汎用的なアルゴリズムへの刷新は、実際に試したところ"price"のような
「主役の属性に過ぎない概念」を誤って主役に昇格させてしまうことを確認
したため、見送った。

**新たに解消したケース**: 「ホテルと観光地を管理したい」が、以前は
`destination`固定だったのに対し、今回`accommodation`が正しく主役に
なった。

→ 詳細: `TECH_DEBT.md` TD24「2026-08-11(2回目)追記」

---

## 4. Design Critic(設計の良し悪しを機械的に評価する仕組み)の評価軸を
8→10へ拡張

M006指示書が定義する14評価軸のうち、これまで8軸だけを実装していた。
今回、以下2軸を追加した。

- **Action Completeness**: データはあるのに、それを操作するActionが
  1つも無い画面(「見るだけで何もできない画面」)を検出する。
- **State Completeness**: アプリ全体でデータが1件も定義されていない
  場合や、画面のデータがアプリ全体のデータ一覧に含まれない「孤立した
  データ」を検出する。

**正直な申告**: 現在のPlanner実装では、これらはほぼ常に満点になる
(Navigation Coherence軸と同じ、将来の複数画面Plan拡張に備えた
防御的な評価軸という位置づけ)。残り4軸(Domain Consistency/Error
Recovery/Explainability/Runtime Safety)は、現在の`evaluate()`が
受け取る情報だけでは機械的に判定できないため見送った。

→ 詳細: `TECH_DEBT.md` TD28

---

## 5. 最大の発見: 「Template」の選定結果が、実際の生成には
一度も使われていなかった

**発見の経緯**: 「Widget・Templateの種類を増やす」を調査する過程で
判明した、今回で最も影響範囲の大きい不具合。

`TemplateSelector`という、11種類のTemplate(checklist/form/tracker/
calendar/memo等)から適切なものを選ぶ、スコアリング・tie-break込みの
本格的な仕組みが既に実装されていた。「満足度アンケート」を実行すると、
実際に内部では正しく`template=form`が選ばれていることも確認した。

**にもかかわらず**、その選定結果を実際にアプリの形へ変換する箇所
(`Compiler.compile()`)へ、選ばれたTemplate名が一度も渡されていな
かった。結果、どのTemplateが選ばれても、常に同じChecklist(買い物
リストのような、チェックボックス付き一覧)形式でしか生成されて
いなかった——Template Selectorの作り込みは、**実際の出力に何の影響も
与えていない死にコードだった**。

**修正**: 選定結果(`template`)をCompile段階へ実際に渡すよう配線し、
`template=="form"`の場合のみ、既存のMock Generator(お手本として実装
済みだった`form_template.py`)と同じ構造(見出し→カード→フォーム→
質問ごとの入力欄→送信で「送信完了」画面へ遷移)で生成するようにした。
**新しいWidget種別は1つも追加していない**(見出し・カード・フォーム
Widgetは、以前から実装・テスト済みのものを再利用しただけ)。

**残り9種のTemplate(tracker/calendar/memo等)は今回未対応**。実際に
選ばれる頻度・必要性を見極めてから、次回以降に判断する。

**実機確認結果**: 「満足度アンケートを作って」が、以前は1つの
チェックリスト画面だったのに対し、今回は「質問3件がそれぞれ独立した
入力欄になった、2画面構成(入力→送信完了)の本物のアンケートフォーム」
になった。本物のBackend Validatorにも正しく通ることを確認した。

→ 詳細: `TECH_DEBT.md` TD29

---

## 6. テスト状況

- forge_ai単体: 415 passed
- backend込み全体: **959 passed, 12 skipped**(前回セッション終了時点
  518+390から大幅増加。今回追加した回帰テストのみで約30件)
- 上記の全修正について、pytestでの確認に加え、実際に`uvicorn`を
  起動し実Gemini APIへリクエストを送る形での実機確認も行った
  (このREADME.md・GETTING_STARTED.mdに記載の手順と同じ方法)。

---

## 7. 今回スコープ外にしたこと(正直な申告)

- **Template拡充は"form"のみ**。tracker/calendar/memo/crud/dashboard/
  catalog/detail_list/wizardは未対応。
- **Design Criticは10/14軸**。残り4軸(Domain Consistency/Error
  Recovery/Explainability/Runtime Safety)は未実装。
- **primary_concept選定の汎用化は、travel 1 Domainの実例に基づく
  最小限の一般化**。他のDomainで同種の問題が今後見つかった場合は、
  `DomainConcept.primary_candidate=False`を追加するだけで対応できる
  設計にはなっている。
- Flutter/Dart側は、この作業環境にSDKが無いため今回も一切実行できて
  いない(バックエンド・forge_ai側のみの変更であり、Flutter側の
  コード自体には触れていないため、直接の影響は無いはずだが、
  実機確認はできていない)。

---

## 8. コミット履歴(このセッション分)

1. `FORGE-AI-QUALITY-001: fix static compile output and 2 domain misclassifications`(TD26・TD27)
2. `FORGE-AI-QUALITY-001: generalize primary_concept selection (TD24 mechanism)`
3. `FORGE-AI-QUALITY-001: extend Design Critic from 8 to 10 evaluated axes`(TD28)
4. `FORGE-AI-QUALITY-001: wire TemplateSelector's "form" choice into Compiler`(TD29)

いずれも`claude/forge-master-handoff-k46jns`へpush済み。
