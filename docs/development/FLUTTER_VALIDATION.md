# Flutter Validation & Environment Notes

`frontend/`をFlutterプロジェクトとして動かす際の、環境固有の注意事項と検証履歴を
まとめる。FORGE-MERGE-003・004での実測に基づく(推測ではなく実測結果)。

---

## 1. 現在の位置付け(Task 4、FORGE-MILESTONE-002.2で更新)

**`frontend/`は、Flutter Application Shell未生成の、Flutter UIソース＋Runtime実装の
状態である。ただしWebプラットフォームのみ、FORGE-MILESTONE-002.2で`web/`一式を
追加し、そのままWeb Buildできる状態にした(2章参照)。**

具体的には:
- `lib/`・`pubspec.yaml`・`analysis_options.yaml`・`test/`・**`web/`**は存在する。
- `android/`・`ios/`・`windows/`・`linux/`・`macos/`・`.metadata`は
  **依然として存在しない**(一度も`flutter create`を通っていないため)。

これは「Flutterパッケージとして解析できない」という意味ではない。実際、
FORGE-MERGE-004でCEO環境の`flutter analyze`は成功している(5章参照)。

### プラットフォーム生成の担当(方針の更新)

**`android/`・`ios/`・`windows/`・`linux/`・`macos/`・`.metadata`の生成は
引き続きCEO環境で行う。** これらはFlutter SDKの実際のリビジョン情報
(`.metadata`)や、プラットフォーム固有のビルド設定(Gradle・Xcode project等、
中身が複雑でClaudeが正確に再現する自信を持てないもの)を含むため、
手作業での再現は避ける(捏造を避ける、という従来の方針を維持)。

**`web/`のみ、方針を変更しClaude側で追加した(2章)。** 理由:
`web/index.html`・`web/manifest.json`は、Flutter公式ドキュメントで
バージョンごとに公開されている、比較的単純で安定したテンプレートであり
(`.metadata`のような不透明なSDK内部情報とは性質が異なる)、Web検索で
現行(2026年7月時点、Flutter 3.44系)の正しいテンプレートを確認した上で
手書きした。ただし実際に`flutter build web`が成功することはClaude環境では
検証できていない(2章参照)。

### CEO環境で実行するコマンド(Android/iOS/Windows等、Web以外)

```powershell
cd C:\forge_verify\frontend   # 実際の検証パスに合わせること
flutter create . --platforms=android
```

Windows Desktopは、Visual Studioの「Desktop development with C++」ワークロード
導入後に追加する。

```powershell
flutter create . --platforms=windows
```

### 既存ファイルへの影響について

`flutter create .`は、Flutter公式のヘルプにおいて「既に存在するプロジェクトに対して
実行した場合、欠けているファイルだけを補って修復する」動作と説明されている
(存在する`lib/`・`pubspec.yaml`を無条件に上書きする動作ではない)。

ただし、**万一に備え、実行前に以下を推奨する**。

1. Gitで管理している場合は、コミット済みの状態で実行する(差分を後で確認できるように)。
2. Gitが無い場合は、`frontend/`フォルダを事前に手動でバックアップする。
3. 実行後、`git diff`または手動比較で`lib/`・`pubspec.yaml`・`analysis_options.yaml`・
   `test/`に意図しない変更が無いことを確認する。

### `test/widget_test.dart` に関する注意(FORGE-RUNTIME-001 Task 7)

`flutter create`は通常、既定のカウンターアプリ用テスト`test/widget_test.dart`
(`MyApp`という存在しないクラスを参照する)を生成する。Forgeの`frontend/`は
一度も`flutter create`を通っていないため、現時点でこのファイルは**存在しない**
(2026-07-11時点で確認済み)。

今後`flutter create . --platforms=...`を実行した際、「欠けているファイル」として
この`widget_test.dart`が新規生成される可能性がある。生成された場合は
`MyApp`(Forgeには存在しないクラス)への参照により`flutter test`が
コンパイルエラーになるため、**生成された場合は速やかに削除するか、
`ForgeApp`を使う内容へ書き換えること**。Forge独自のテスト
(`smoke_test.dart`等)とは別物であり、削除してもForgeのテストカバレッジには
影響しない。

---

## 2. Web構成の詳細(FORGE-MILESTONE-002.2で追加)

`frontend/web/`に以下を追加した。実際に`flutter create . --platforms web`を
実行して生成したものではなく、Flutter公式ドキュメント
(`docs.flutter.dev/platform-integration/web/initialization`、2026年7月時点、
Flutter 3.44.0向けの記述として確認)を根拠に手書きしたものである。

```
web/
├── favicon.png              (32x32、生成画像)
├── index.html
├── manifest.json
└── icons/
    ├── Icon-192.png          (192x192、生成画像)
    ├── Icon-512.png          (512x512、生成画像)
    ├── Icon-maskable-192.png (192x192、セーフゾーン付き)
    └── Icon-maskable-512.png (512x512、セーフゾーン付き)
```

- `index.html`・`manifest.json`: 現行Flutter(post-3.22系、`flutter_bootstrap.js`
  方式)の標準テンプレートに、`pubspec.yaml`の`name`(`forge_app`)・
  `description`を反映させたもの。`flutter_bootstrap.js`自体はこのリポジトリに
  含めていない — `flutter build web`がビルド時に自動生成する既定の仕組みで
  あることを公式ドキュメントで確認済みのため、含める必要が無い。
- アイコン5点: Pythonの`Pillow`ライブラリで実際に生成した、有効なPNGファイル
  (ForgeThemeのaccent色を背景に「F」の文字)。実際のブランドロゴではなく、
  技術的に有効なプレースホルダーである。

**`.metadata`との違い(なぜ今回は手書きしたか)**: `.metadata`はFlutter SDKの
実際のgitリビジョンハッシュ等、Claudeが知りようのない不透明な情報を含むため
引き続き作成しない。一方`web/index.html`・`manifest.json`はFlutterが
バージョンごとに公開している比較的単純なテンプレートであり、Web検索で
現行版を確認した上で再現可能だったため、今回に限り方針を変えた。

**確認できていないこと**: 上記一式で実際に`flutter build web`が成功するかは、
Claude環境にFlutter SDKが無いため検証できていない。CEO環境での実行結果を
待つ必要がある。

---

## 3. パスとシェルに関する注意事項(Task 5)

**以下はFORGE-MERGE-003〜004での実測結果であり、Flutter一般の確定仕様として
断定するものではない。**

FORGE-MERGE-003時点(PowerShell経由、日本語を含む可能性のあるパス/OneDrive配下)では、
`flutter analyze`実行時にAnalysis Serverが`FormatException`で異常終了する事象が
発生した。FORGE-MERGE-004で、検証パスを`C:\forge_verify\frontend`(短いASCIIパス)へ
変更し、`cmd.exe`経由で実行したところ、同じ事象は再現せず、`flutter analyze`・
`dart analyze`とも正常終了した(`docs/reports/FORGE-MERGE-004-report.md` 6章
「過去の原因仮説の訂正」参照)。

この2点(パスの文字種・実行シェル)のどちらが、あるいは両方が影響したのかは、
今回の実測だけでは確定できていない。**「Flutterは日本語パスやPowerShellで
必ず失敗する」という一般化はしないこと**。あくまで今回のケースで役に立った
回避策として記録する。

### 推奨される検証手順

1. 可能な限り、短いASCIIパスで検証・ビルドを行う(例: `C:\forge`、`C:\forge_verify`)。
   OneDrive等のクラウド同期フォルダ配下は避ける。
2. 問題が発生した場合は、`cmd.exe`経由でも再試験する。
3. 上記1・2をどちらも試して問題が解消しない場合は、Flutter/Dartの実際のエラー
   メッセージ全文・スタックトレースを記録し、`flutter doctor -v`の出力とあわせて
   報告する。

---

## 4. Mock Mode / Live Mode(FORGE-RUNTIME-001)

`frontend/`は`AppConfig.current.mockMode`(既定値`true`)により、Backendを
一切使わずに動作する「Mock Mode」と、実際に`POST /api/v1/ai/generate`を
呼ぶ「Live(HTTP) Mode」を切り替えられる。詳細は`README.md`の該当セクションを参照。

```powershell
# Mock Mode(既定。Backend起動不要)
flutter run -d chrome

# Live Mode(Backendを起動した上で)
flutter run -d chrome --dart-define=FORGE_MOCK_MODE=false
```

画面右上のBadge(`MOCK`/`LIVE`)で現在のモードを確認できる。

## 5. 検証履歴

| 日付 | 環境 | 結果 |
|---|---|---|
| FORGE-MERGE-003 | PowerShell、パス詳細不明(OneDrive配下または日本語パスの可能性) | `flutter analyze`がFormatExceptionでAnalysis Server crash。`flutter test`はテスト不在。`flutter build windows`はプラットフォーム未構成 |
| FORGE-MERGE-004 | Flutter 3.44.5 / Dart 3.12.2 / Windows 10 / `C:\forge_verify\frontend` / cmd.exe経由 | `flutter clean`・`flutter pub get`・`dart analyze`・`flutter analyze`いずれも成功。`flutter analyze`はinfo 1件のみ(`withOpacity`非推奨、本レポート提出版で修正済み)。`flutter test`はテスト未反映の旧ローカルRepositoryで実施されたため未検証。Web/Windows Buildはプラットフォーム未生成のため未実施 |
| FORGE-MERGE-005 | 同上、`C:\forge_verify\files (2)\forge-v0.2-integrated\forge\frontend` | `flutter test`: **7/7 PASS**。`flutter analyze`: Error 0 / Warning 3(`MaterialPageRoute`型引数、修正済み) |
| FORGE-RUNTIME-002 | `C:\forge_verify\runtime002\forge\frontend` | Flutter Test 94件成功・E2Eテスト1件失敗(Generated Screen本文が空白、RenderBox関連例外)。根本原因はFORGE-RUNTIME-003で特定・修正 |
| FORGE-RUNTIME-003 | (FORGE-MILESTONE-002依頼書内の前提共有として報告) | `flutter analyze` No issues found!・`flutter test` 103/103 PASS・Chrome実機でHome→Confirm→Generated Screen→チェックリスト操作まで成功 |
| FORGE-MILESTONE-002.1 | `C:\forge_verify\milestone002_1\forge\frontend` | Python 135/135 PASS・**Flutter Test 166/166 PASS**・Web Build PASS・`flutter analyze` 3 issues(修正済み) |
| FORGE-MILESTONE-002.2 | (提出物のみ、CEO実測はまだ) | `frontend/web/`欠如により`flutter build web`が`This project is not configured for the web`で失敗した報告を受け、`web/`一式を追加。Web Buildが成功するかは未検証(2章参照) |

今後の検証結果もこの表に追記していくこと(上書きせず、行を追加する)。
