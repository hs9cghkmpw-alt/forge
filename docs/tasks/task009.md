# Task009 — FORGE-RUNTIME-002: Generated Screen Rendering Fix & Navigation E2E Verification

## 依頼内容
- CEO実機で確認された不具合(Generated Screen本文が空白、RenderBox関連の
  例外らしきログ)の根本原因をJSON生成・パース・Renderer各段階で切り分ける。
- 実際の生成JSON(子どもカテゴリ)をレポートへ掲載する。
- Renderer/Widget Registryを監査し、最小変更で修正する。ハードコードや
  例外の握り潰しは禁止。
- チェックリスト項目の複数表示・操作(チェック/削除)を成立させる。
- Home→Confirm→Generated Screenの実際の生成フローを検証する
  Widget Test(E2E相当)を追加する。
- Mock Generatorが出力する8カテゴリ全てについて、Rendererで実際に
  描画可能であることを検証する契約テストを追加する。
- TD10(Python/Dart二重管理)は解消済み扱いにせず、共通ドキュメント化と
  差分確認だけ行う。

## 行った変更
- 実際にPython Mock Generatorを実行し、「子どもの持ち物チェックを作って」の
  生成JSON(5項目、Validator合格)を取得してレポートに掲載した。
- JSON生成→パース→State格納の各段階を実際にコード追跡し、データが
  失われていないことを確認した(問題はレイアウト/hit-test段階と判断)。
- `widget_registry.dart`の`_buildChecklist`を3点修正(内側Columnの
  mainAxisSize明示、ListTileへのKey付与、leadingのIconButton化)。
- Task 4の指定リスト(Expanded/Flexible/ListView/Positioned/LayoutBuilder/
  Offstage/Visibility/Stack等の誤用パターン)をリポジトリ全体でgrep監査し、
  該当箇所が無い(または正しく使われている)ことを確認した。
- `test/e2e/kids_checklist_generation_flow_test.dart`新設。Home→カードタップ
  →Confirm→生成→チェックリスト表示→チェック操作までを1テストで検証。
  ローディング中の`CircularProgressIndicator`(無期限アニメーション)を
  考慮し、`pumpAndSettle()`ではなく明示的な`pump(Duration)`を使用。
- `test/features/app_generation/data/datasources/
  mock_generator_renderer_contract_test.dart`新設。8カテゴリ×8観点=64件。
- `docs/spec/MOCK_GENERATOR_CONTRACT.md`新設。Python版・Dart版の
  9カテゴリをプログラムで機械比較し、差分0件であることを確認した。
- `TECH_DEBT.md`: TD10を解消済みにはせず更新、TD11(レイアウト時例外の
  保護が無いという構造的限界)を新規追加。

## 変更理由
「事実と推測を厳密に分離する」に従い、根本原因を1つに断定できるだけの
情報(完全なスタックトレース)が無いことを正直に記録した上で、
独立して正当化できる3つの改善を適用する、という方針を取った。
Renderer全面書き換え・Widget追加・「子ども」カテゴリだけの特別処理は
いずれも行わず、既存の6 Widget種の実装の中で完結する修正にとどめた。
