# Task005 — FORGE-MERGE-003: Flutterプロジェクトとしての成立性

## 依頼内容
- CEO環境での実測結果(`flutter analyze`/`flutter test`/`flutter build windows`が
  FAIL)を踏まえ、Analysis Server crash(FormatException)の原因調査。
- Flutter Test(Widget Test・Smoke Test)の追加。
- `windows/`ディレクトリが存在しない理由・意図の調査(勝手に生成しない)。
- Analyzerが動作した場合に想定されるエラーの事前レビュー。
- Desktop Project生成・`flutter create`・Backend変更・Language変更は禁止。

## 行った変更
- `frontend/`が一度も`flutter create`を通っていないことを、ディレクトリ一覧の
  直接確認により確定させた(android/ios/windows/linux/macos/web/analysis_options.yaml/
  .metadataがすべて欠如)。
- Web検索により、症状が一致する実例(dart-lang/sdk#41322、package_config.json
  解決時のFormatException)を発見し、優先度付き候補リストの第1候補とした。
- `frontend/analysis_options.yaml`を新設(`flutter_lints`を実際に有効化)。
  FormatExceptionの根本原因を解消する保証は無いと明記した。
- `frontend/test/`に3ファイル・7件のテストを新設(smoke 1件・HomeScreen 4件・
  ForgeFallbackWidget 2件)。`.gitkeep`を削除。
- `windows/`欠如の意図について、flutter create未実施(可能性高)とRepository方針
  (痕跡なし、可能性低)の2択を提示し、断定せずCEOに確認を求めた。
- `flutter_lints`の主要ルール(prefer_single_quotes・sort_child_properties_last・
  avoid_print・use_super_parameters・コード生成非依存)を手動で突き合わせ、
  全て問題なしと確認した。断定できない項目(型推論の細部・未使用private
  メンバー)は「予測」であり「確認」ではないと明記した。
- `.metadata`は実際のSDK情報を持たないため作成しなかった(DECISIONS.md D16)。

## 変更理由
指示書の「最重要事項: CEO環境の実測結果を最優先とする。推測で『Analyzerは
通るはず』と判断しない」に従い、以下を徹底した。
1. 確定した事実(ディレクトリ構成)と、確定していない事実(FormatExceptionの
   正確な原因)を明確に分離した。
2. 断定できない箇所は、Web検索で見つけた実例による裏付けの有無を明記した上で、
   優先順位付きの「候補」として提示した(1つに決め打ちしなかった)。
3. 原因が未確定のまま実施した修正(analysis_options.yaml)については、
   「これが直接の解決策である」という主張はせず、独立して正当な理由を明記した。
4. `.metadata`のように、Claudeが持っていない情報(実際のSDKリビジョン)を
   捏造すれば「解決したように見せる」ことができる場面でも、捏造しなかった。
