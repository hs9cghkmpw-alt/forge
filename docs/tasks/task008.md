# Task008 — FORGE-RUNTIME-001: Runtime Mock Mode & First Interactive Experience

## 依頼内容
- Backendが存在しなくてもForge全体(Home→Confirm→生成→Renderer)を
  操作できるMock Modeを追加する。AI品質ではなくRuntime体験の完成を目的とする。
- `AppConfig.mockMode`の追加、Repository(Http/Mock)の分離とDI切り替え、
  既存Mock GeneratorのRepository経由利用、Loading表示、Error UX簡潔化、
  成功体験の一気通貫、widget_test.dart整理、Mock/Live Badge、
  構造化ロギング、README更新。
- Widget追加・UI全面改修・Language/Validator/Backend/Runtime設計変更は禁止。

## 行った変更
- `core/config/app_config.dart`新設。`mockMode`(既定`true`、
  `--dart-define=FORGE_MOCK_MODE=false`で上書き可)と`apiBaseUrl`を持つ。
- `core/utils/forge_logger.dart`新設。新規パッケージ依存を避け、
  `debugPrint`を内部で使う薄いラッパーにした。
- `data/datasources/mock_generation_datasource.dart`新設。Python版
  `mock_generator.py`のDart移植(HTTP不要でMock Modeを完結させるため)。
- `data/repositories/app_generation_repository_impl.dart`を
  `http_app_generation_repository.dart`へ改名(`HttpAppGenerationRepository`)。
  ユーザー向けエラーメッセージを簡潔化し、詳細は`ForgeLogger`へ。
- `data/repositories/mock_app_generation_repository.dart`新設。
  意図的な650ms遅延を加え、構造上例外を投げない設計にした。
- `presentation/providers/app_generation_provider.dart`を更新し、
  `AppConfig.current.mockMode`でHttp/Mockを切り替えるようにした。
- `presentation/screens/generated_app_screen.dart`: loading状態にAppBar
  (戻るボタン)を追加。エラー画面の文言を簡潔化。
- `presentation/screens/confirm_screen.dart`: `_isSubmitting`フラグで
  ボタン連打を防止。
- `main.dart`: `MaterialApp.builder`でFlutter標準の`Banner`を使い、
  MOCK/LIVEのBadgeを追加。`debugShowCheckedModeBanner`は変更せず。
- `test/features/app_generation/data/datasources/
  mock_generation_datasource_test.dart`新設。6ファイル中の呼び出し箇所は
  6だが、うち2箇所がループで8件・11件を生成するため、実質23件のテストケース
  (Python版と同じ8カード全対応の回帰テスト・判定順衝突の回帰テスト・
  `ForgeDocument.fromJson()`への疑似E2Eパース確認を含む)。
- `docs/development/FLUTTER_VALIDATION.md`にMock Mode節・
  `widget_test.dart`に関する注意(Task 7)・検証履歴を追記。
- `README.md`のセットアップ手順をCEO実測ベースの内容へ更新し、
  Mock Mode/Live Modeの切り替え方法を追記。
- `docs/DECISIONS.md`へD21〜D25、`TECH_DEBT.md`へTD10を追記。

## 変更理由
既存のRepository interfaceパターン(FORGE-MERGE-001で既に導入済み)を
そのまま活用し、画面側のコードを一切変更せずにHttp/Mockの切り替えを
実現した。Mock Generatorの二重管理(Python/Dart)は、D8の前提
(Backend経由での差し替え)と今回の要求(Backend非依存)が両立しないために
生じた、正直に受け入れるべきトレードオフとして記録している。
