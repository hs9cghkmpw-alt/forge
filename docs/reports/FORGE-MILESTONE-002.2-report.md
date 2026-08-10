# FORGE-MILESTONE-002.2 実施レポート — Web Platform Files Inclusion

**Ref:** FORGE-MILESTONE-002.2　**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-11

---

## 1. 今回の欠落原因

`frontend/`は、FORGE-MERGE-001以降一度も`flutter create`を通していない
(`lib/`・`pubspec.yaml`等を手作業で用意した状態からスタートしている)。
これは意図的な方針だった: `.metadata`やプラットフォームファイルは
Flutter SDKの実際のリビジョン情報等、Claudeが確実に知り得ない情報を含むため、
**Claude側では捏造せずCEO環境での生成に委ねる**、という判断を
FORGE-MERGE-004以来一貫して取っていた(`docs/development/
FLUTTER_VALIDATION.md`に明記済み)。

その結果、`web/`を含む全プラットフォームディレクトリが存在しないまま
複数回のマイルストーンが進み、FORGE-MILESTONE-002.1のレポートで
「Web Build PASS」という**CEO実測結果**を記載したにもかかわらず
(CEO環境では別途`flutter create`済みの状態で検証されたと推測される)、
**Claude側が提出するZIP自体には`web/`を含めていなかった**という不整合が
生じていた。この不整合をレポート内で明示的に警告していなかったことが、
今回の問題の直接的な原因である。

**今回の対応**: `web/`に限り方針を変更し、Claude側で追加した(2章)。
`android/`・`ios/`・`windows/`・`linux/`・`macos/`は、プラットフォーム固有の
複雑なビルド設定(Gradle・Xcode project等)を含むため、引き続きCEO環境での
生成が必要という判断を維持している(理由は`docs/DECISIONS.md` D38)。

---

## 2. 追加・変更されたファイル一覧

### 新規追加(`frontend/web/`、7ファイル)

| ファイル | 内容 |
|---|---|
| `frontend/web/index.html` | Flutter公式テンプレート(Flutter 3.44.0向け記述で確認)を手書き |
| `frontend/web/manifest.json` | PWAマニフェスト(同上) |
| `frontend/web/favicon.png` | 32×32、Pillowで生成した有効なPNG |
| `frontend/web/icons/Icon-192.png` | 192×192、同上 |
| `frontend/web/icons/Icon-512.png` | 512×512、同上 |
| `frontend/web/icons/Icon-maskable-192.png` | 192×192、セーフゾーン付き |
| `frontend/web/icons/Icon-maskable-512.png` | 512×512、セーフゾーン付き |

### 更新(3ファイル)

| ファイル | 内容 |
|---|---|
| `docs/development/FLUTTER_VALIDATION.md` | プラットフォーム生成方針を更新、Web構成の詳細節を新設、検証履歴に不足分を追記 |
| `README.md` | セットアップ手順に`flutter build web --debug`を追加 |
| `CHANGELOG.md` / `docs/DECISIONS.md`(D38) / `docs/tasks/task013.md` | 記録 |

`frontend/web/flutter_bootstrap.js`は**意図的に含めていない**。Flutter公式
ドキュメントで、この既定ファイルは`flutter build web`実行時にビルドツールが
自動生成する仕組みであることを確認したため(1件目のWeb検索結果、
`docs.flutter.dev/platform-integration/web/initialization`)。

---

## 3. 影響範囲(差分監査、依頼書項目3)

**`frontend/web/`配下以外は1バイトも変更していない。** 以下を実際に
ファイル内容を再取得して確認した(推測ではない)。

| 確認対象 | 結果 |
|---|---|
| `pubspec.yaml` | 変更前と完全一致(`flutter:`セクションへのweb関連キー追加等は無し) |
| `analysis_options.yaml` | 変更前と完全一致 |
| `lib/main.dart`(エントリポイント) | 変更前と完全一致 |
| Language(`shared/schemas/`) | 変更対象外(未着手) |
| Runtime(`lib/json_ui/`) | 変更対象外(未着手) |
| 既存テスト(Python 135件・Dart全ファイル) | 変更対象外。Python 135件を再実行し合格を再確認 |
| AI Foundation | 変更対象外(未着手) |

今回`flutter create`コマンドそのものは一度も実行していない(実行できる
Flutter SDKが無いため)。したがって「自動生成によって既存ファイルが
意図せず書き換えられる」というリスク経路自体が存在しない
(手書き・新規追加のみのため、副作用が構造的に発生し得ない)。

---

## 4. 提出前のZIP内容監査(依頼書項目6)

再提出ZIPを展開して`frontend/web/`の実在を直接確認した。

```
frontend/web/index.html            存在確認済み
frontend/web/manifest.json         存在確認済み(有効なJSONとして解析済み)
frontend/web/favicon.png           存在確認済み(有効なPNG、32x32として解析済み)
frontend/web/icons/Icon-192.png            存在確認済み(有効なPNG、192x192)
frontend/web/icons/Icon-512.png            存在確認済み(有効なPNG、512x512)
frontend/web/icons/Icon-maskable-192.png   存在確認済み(有効なPNG、192x192)
frontend/web/icons/Icon-maskable-512.png   存在確認済み(有効なPNG、512x512)
```

ZIPの最上位が`forge/`のみであること(余計な親フォルダが無いこと)も確認済み。

---

## 5. 実際に検証できたこと

- `frontend/web/manifest.json`が有効なJSONであることをパースして確認。
- 5点のPNGファイルすべてが、実際にPillowで開いて`verify()`を通過する
  有効な画像であり、意図した寸法(32x32・192x192・512x512)であることを確認。
- Python 135件のテストを再実行し、合格を再確認(今回の変更が無関係であることの確認)。
- `pubspec.yaml`・`analysis_options.yaml`・`lib/main.dart`の内容を再取得し、
  変更前と一致することを確認。
- Web検索により、`index.html`・`manifest.json`の構造が現行Flutter(3.44系、
  `flutter_bootstrap.js`方式)の公式テンプレートと一致することを、
  複数の情報源(公式ドキュメント含む)で確認。

---

## 6. 実際に検証できていないこと(最重要)

| 項目 | 状態 |
|---|---|
| `flutter build web`が実際に成功するか | **未検証。** Claude環境にFlutter SDKが無く、実行手段が無い |
| `flutter build web`実行後、Chrome等で実際にアプリが起動するか | **未検証** |
| `index.html`・`manifest.json`の内容が、CEO実機のFlutter 3.44.5と
  完全に互換であるか | **未検証。** Web検索による確認はしたが、実際のビルド結果ではない |
| `flutter analyze`・`flutter test`が引き続き成功するか | **未検証。** `web/`追加がこれらに影響するとは考えにくいが断定しない |

**もし`flutter build web`が今回も失敗する場合、表示された正確なエラー
メッセージ全文を共有してほしい。** それが無いと、これ以上の絞り込みは
困難である(FORGE-MERGE-003→004で完全なスタックトレースを得て初めて
根本原因を特定できた、という過去の経緯と同じ理由による)。

---

## 7. CEO再検証手順

```powershell
cd "C:\forge_verify\<今回の展開先>\forge\frontend"
flutter clean
flutter pub get
flutter analyze
flutter test --reporter expanded
flutter build web --debug
```

すべてZIPを展開しただけの状態で成功することを目指しているが、6章の通り
`flutter build web`の成功はClaude環境では断定できていない。
