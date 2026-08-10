# Task006 — FORGE-MERGE-004: Flutter Analyze Fix & Repository Completion

## 依頼内容
- CEO実機での実測(Flutter 3.44.5、ASCIIパス、cmd.exe経由)により、
  `flutter analyze`が成功しinfo 1件(`withOpacity`非推奨)のみだったことが判明。
  これを修正する。
- 前回追加した7件のFlutter Testが、今回提出するRepositoryに確実に含まれることを
  保証し、ファイル単位で一覧化する。
- Flutter Testの静的監査(実行はできないため)。
- プラットフォーム構成方針の明文化。CEO環境での`flutter create`実行を前提とし、
  Claude側では生成しない。
- パス・シェルに関する注意事項の追記(一般化しない)。
- 前回レポートの誤った仮説(package_config.json起因説、flutter create未実施が
  4つのFAILすべての共通原因という説)を、実測に基づき訂正する。過去のレポートは
  削除しない。
- ドキュメント同期。

## 行った変更
- `home_screen.dart`の`withOpacity(0.6)`を`withValues(alpha: 0.6)`へ置換
  (公式移行ガイドで確認した正しい置換方法)。リポジトリ全体を検索し、他に
  該当箇所が無いことを確認した。
- `test/`配下の3ファイル・7件を再確認し、Task 3の監査チェックリスト
  (import解決/class名/constructor引数/pumpWidget対象/Provider依存/
  pumpAndSettle/finderの一意性/表示文字列/private API依存/deprecated API)
  に沿って再点検した。1件、finderの一意性に関する不確実性
  (`find.text()`がTextField内部の表示内容まで拾うかどうか断定できない箇所)を
  発見し、`TextField.controller.text`を直接読む形に修正した。
- `docs/development/FLUTTER_VALIDATION.md`を新設。プラットフォーム生成方針
  (Task 4)・パス/シェルの注意事項(Task 5)・検証履歴表をまとめた。
- `ci.yml`のFlutterバージョン指定を、根拠のない暫定値(3.22.0)から
  CEO実機の実測値(3.44.5)へ更新した。
- `docs/reports/`を新設し、FORGE-MERGE-001〜003の過去レポートをそのまま保存。
  FORGE-MERGE-003-report.mdの冒頭に訂正内容へのポインタを追記(本文は無改変)。
- `docs/DECISIONS.md`へD18〜D20を追記。

## 変更理由
指示書の「今回も、実行できなかったFlutterコマンドを『合格』『完了』と報告しては
ならない」という原則を継続した。CEO実機での実測により初めて確定した事実
(`withOpacity`のみが唯一の指摘事項であったこと、package_config.json仮説の
反証)を、過去の記述を消さずに訂正として積み上げる形で記録した。
