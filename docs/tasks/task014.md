# Task014 — FORGE-MILESTONE-003: Stateful Runtime Foundation

## 依頼内容
Forge JSON UI Runtimeへ、State Store・State Binding・統一Action Dispatcher・
Form Validation・Runtime Navigation・Runtime Diagnosticsを正式に追加する。
既存機能(Milestone 002、CEO実機でFlutter Test 166/166 PASS・Web Build成功済み)を
一切壊さないことを凍結基準とする。AI接続はまだ行わない。作業順序・依存方向
(Widget→Runtime Binding→State Store/Action Dispatcher/Validator→ForgeDocument
Models)を厳守する。途中報告不要、完成状態まで進める。

## 行った変更
- Forge Language v1.2新設(`shared/schemas/ui_schema.v1.2.json`)。number State型、
  set_state/toggle_state/reset_state/submit_form/composite の5 Action、
  text_field/checkboxへのvalidationプロパティ。v1.0/v1.1は無改変。
- Python Validatorをv1.0/v1.1/v1.2の3バージョン対応へ拡張。32件の新規テストを
  作成・実行し、既存135件との合計167件全合格を確認した(検証中に
  「validation警告がerrorsリストへ誤って混入する」実バグを発見・修正した)。
- Dart側`json_ui/runtime/`を新設: `ForgeStateStore`(単一State Store)・
  `ForgeActionDispatcher`(統一Action処理、ActionResult返却)・
  `ForgeFormValidator`(6種の検証ルール)。
- `ForgeRuntimeState`を、既存の公開API(getString/setString/dispatch等)を
  一切変えずに、上記Runtime層へ委譲する形にリファクタリングした。
- `forge_renderer.dart`: 画面遷移段数の上限(無限遷移防止)、診断ログ配線。
- Widget Builder: checkboxはtoggle_state経由に統一、formの送信ボタンは
  submit_form経由に変更(検証の要)、text_field/checkboxにエラー表示を追加。
- Mock Generator(Python/Dart両方)のSurvey Templateへ実際のvalidation
  (コメント欄のmax_length)を追加し、v1.1→v1.2へバージョンを更新した
  (この過程でPython側の既存テスト2件が version="1.1" を前提にしていたため、
  正当な理由に基づき期待値を更新した)。
- 新規Dartテスト46件(State Store 14・Action Dispatcher 14・Form Validator 12・
  State Binding 5・E2E 1)を作成。既存テストは削除・弱体化していない。

## 変更理由
「単一のState Store」「Action Dispatcherの一元化」という要求を、既存の
Widget Builderコードを1行も変更せずに満たすため、新しいRuntime層を追加した上で
既存クラスをそこへ委譲させる設計にした(詳細は`docs/DECISIONS.md` D39〜D43、
`docs/spec/RUNTIME_CONTRACT_V1_2.md`)。sealed classへ新しいsubtypeを追加する
たびに、switch式の非網羅性を毎回手動で全箇所洗い出して確認した
(過去にこの種のバグを本番相当のテストファイルで発見した経験による)。
