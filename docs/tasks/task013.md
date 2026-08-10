# Task013 — FORGE-MILESTONE-002.2: Web Platform Files Inclusion

## 依頼内容
CEOがFORGE-MILESTONE-002.1の成果物ZIPで`flutter build web`を実行したところ、
`frontend/web/`が存在せず`This project is not configured for the web`で
失敗した。ZIP内を確認しても`frontend/web/`が無いことが確認された。以下を要求された。

1. 正しいFlutter Webプラットフォームファイル一式を`frontend/web/`として含める。
2. CEO側で`flutter create . --platforms web`を実行しなくても、そのまま
   Web Buildできる成果物にする。
3. 自動生成時に既存コード・pubspec.yaml・lint設定・テスト・エントリーポイントを
   意図せず変更していないことを差分監査する。
4. 修正済みの完全なZIPを再提出する。
5. レポートに欠落原因・追加変更ファイル一覧・影響範囲を追記する。
6. 提出前にZIP内容を監査し、`web/index.html`等が実際に含まれることを確認する。

## 行った変更
- `frontend/web/index.html`・`manifest.json`を新設。Flutter公式ドキュメント
  (Flutter 3.44.0向け記述として確認)を根拠に手書きした。
- `frontend/web/favicon.png`・`icons/Icon-{192,512}.png`・
  `icons/Icon-maskable-{192,512}.png`を新設。Pillowで実際に生成し、
  有効なPNGファイルであることを確認した。
- `docs/development/FLUTTER_VALIDATION.md`を更新し、プラットフォームファイル
  生成方針を「`web/`のみClaude側で追加、他は引き続きCEO環境」へ変更したことと
  その理由を明記した。検証履歴表に過去の未記録分(RUNTIME-002/003)も含め追記した。
- `README.md`のセットアップ手順に`flutter build web --debug`を追加。
- 差分監査: `pubspec.yaml`・`analysis_options.yaml`・`lib/main.dart`の内容を
  実際に再確認し、1バイトも変更されていないことを確認した。Python 135件を
  再実行し無影響を確認した。

## 変更理由
`.metadata`(Flutter SDKの不透明な内部情報)と`web/index.html`・
`manifest.json`(公開されたバージョン別テンプレート)は性質が異なると判断し、
後者に限り「Claude側では生成しない」という従来方針を変更した(理由の詳細は
`docs/DECISIONS.md` D38)。`flutter create`コマンドは実行していない
(Claude環境にFlutter SDKが無いため物理的に実行不可能)。すべて手書き・
プログラムでのPNG生成であり、実際に`flutter build web`が成功することは
検証できていない。
