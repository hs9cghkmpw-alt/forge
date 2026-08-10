# FORGE-RUNTIME-001 実施レポート — Runtime Mock Mode & First Interactive Experience

**Ref:** FORGE-RUNTIME-001　**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-11

CEO実測(Python Validator 97/97・`flutter analyze` No issues found!・`flutter test` 7/7 PASS・
Chrome起動成功)を土台に、Backend非依存で操作できるMock Modeを追加した。
今回の変更後の`flutter analyze`/`flutter test`は未実行であり、断定しない。

---

## 1. 修正ファイル一覧

### 新規
| ファイル | Task |
|---|---|
| `frontend/lib/core/config/app_config.dart` | 1 |
| `frontend/lib/core/utils/forge_logger.dart` | 9 |
| `frontend/lib/features/app_generation/data/datasources/mock_generation_datasource.dart` | 3 |
| `frontend/lib/features/app_generation/data/repositories/mock_app_generation_repository.dart` | 2 |
| `frontend/lib/features/app_generation/data/repositories/http_app_generation_repository.dart` | 2(旧`app_generation_repository_impl.dart`を改名) |
| `frontend/test/features/app_generation/data/datasources/mock_generation_datasource_test.dart` | 3 |
| `docs/tasks/task008.md` | 全体 |

### 変更
| ファイル | Task |
|---|---|
| `frontend/lib/core/network/dio_client.dart` | 1(baseUrlをAppConfigへ統合) |
| `frontend/lib/features/app_generation/presentation/providers/app_generation_provider.dart` | 1・2 |
| `frontend/lib/features/app_generation/presentation/screens/generated_app_screen.dart` | 4・5 |
| `frontend/lib/features/app_generation/presentation/screens/confirm_screen.dart` | 4 |
| `frontend/lib/main.dart` | 8 |
| `docs/development/FLUTTER_VALIDATION.md` | 4・7 |
| `README.md` | 10 |
| `docs/DECISIONS.md` | 全体(D21〜D25) |
| `TECH_DEBT.md` | 全体(TD10) |
| `CHANGELOG.md` | 全体 |

### 削除
| ファイル | 理由 |
|---|---|
| `frontend/lib/features/app_generation/data/repositories/app_generation_repository_impl.dart` | `http_app_generation_repository.dart`へ改名のため |

### 確認のみ(変更なし)
`frontend/test/widget_test.dart` はTask 7の対象だが、現時点で**存在しないことを
確認した**(2026-07-11時点、`flutter create`未実施のため)。将来`flutter create`
実行時に生成される可能性への対処法を`docs/development/FLUTTER_VALIDATION.md`に
記載した。

---

## 2. Mock Mode構成図

```
AppConfig.current.mockMode (既定 true, --dart-define=FORGE_MOCK_MODE=false で上書き)
        │
        ▼
presentation/providers/app_generation_provider.dart
   (_appGenerationRepositoryProvider が分岐)
        │
   mockMode?
    ┌───┴───┐
   true    false
    │        │
    ▼        ▼
MockAppGenerationRepository      HttpAppGenerationRepository
    │                                   │
    ▼                                   ▼
MockGenerationDataSource            AiGenerationApi (Dio)
  (Dart, HTTP通信なし)                    │
    │                                   ▼
    │                          POST /api/v1/ai/generate
    │                          (Backend起動が必要)
    ▼                                   ▼
Forge JSON(Map)                   Forge JSON(Map)
    │                                   │
    └───────────────┬───────────────────┘
                     ▼
         GenerateAppUseCase → ForgeDocumentView(Runtime)
```

画面(`GeneratedAppScreen`等)はこの分岐を一切知らない
(`AppGenerationRepository`インターフェースしか参照しない)。

---

## 3. Repository構成図

```
domain/repositories/app_generation_repository.dart
  abstract class AppGenerationRepository
    Future<Map<String, dynamic>> generate(String text)
                    ▲                        ▲
                    │ implements             │ implements
                    │                        │
  HttpAppGenerationRepository      MockAppGenerationRepository
  (旧AppGenerationRepositoryImpl)   (新規)
    - AiGenerationApi(Dio)            - MockGenerationDataSource
    - 実際のHTTP通信                    - HTTP通信なし、650ms遅延のみ
    - 失敗時: AppGenerationException   - 構造上例外を投げない
      (簡潔なメッセージ、詳細はログ)
```

画面が依存するのは`GenerateAppUseCase`(`domain/usecases/`)のみで、
そこから`AppGenerationRepository`インターフェースを参照する。
DIでの実体選択は`presentation/providers/app_generation_provider.dart`
1箇所に閉じている。

---

## 4. Runtimeシーケンス図(Mock Mode、Task 6の一気通貫フロー)

```
User                HomeScreen        ConfirmScreen      GeneratedAppScreen        Riverpod/Repository層           Runtime(json_ui/)
 │                      │                   │                    │                          │                          │
 │─文章入力/カードタップ→│                   │                    │                          │                          │
 │                      │                   │                    │                          │                          │
 │─「これで作る」タップ→│                   │                    │                          │                          │
 │                      │─push(ConfirmScreen)→                   │                          │                          │
 │                      │                   │                    │                          │                          │
 │──「この内容で作ります」タップ──────────→│(_isSubmitting=true、連打防止)                  │                          │
 │                      │                   │─pushReplacement(GeneratedAppScreen)──────────→│                          │
 │                      │                   │                    │─ref.watch(appGenerationProvider)→                   │
 │                      │                   │                    │  (loading: AppBar+CircularProgressIndicator表示)     │
 │                      │                   │                    │                          │─MockAppGenerationRepository.generate()
 │                      │                   │                    │                          │   ForgeLogger: START/REQUEST
 │                      │                   │                    │                          │   await 650ms
 │                      │                   │                    │                          │   MockGenerationDataSource.generate(text)
 │                      │                   │                    │                          │   ForgeLogger: SUCCESS
 │                      │                   │                    │←──Forge JSON(Map)────────│                          │
 │                      │                   │                    │─ForgeDocumentView(rawJson)──────────────────────────→│
 │                      │                   │                    │                          │      ForgeDocument.fromJson()
 │                      │                   │                    │                          │      → ForgeScreenView描画
 │←─────────────────────操作可能なチェックリストが表示される(体感上「AIが作った」ように見える)─────────────────────────│
```

Home/Confirmが自前の遷移先を知っているのは今まで通り(Task 2で変更していない)。
変わったのは`GeneratedAppScreen`から先、Repositoryの実体だけである。

---

## 5. 実際に検証できたこと(Claude環境で実行できたコマンドのみ)

- Python: 97件のValidator/Generatorテストを再実行し、合格を再確認
  (今回の変更はDart側のみのため無影響であることの確認)。
- Dartファイル(24ファイル、`lib/`+`test/`)の中括弧・丸括弧対応、
  `package:forge_app/...`形式のimport解決: 機械チェックで問題0件。
- 識別子の定義-参照突合(新規クラス`AppConfig`/`ForgeLogger`/
  `MockGenerationDataSource`/`HttpAppGenerationRepository`/
  `MockAppGenerationRepository`を含む): 全件定義箇所を確認。
  旧クラス名`AppGenerationRepositoryImpl`への実コード参照が残っていないことも確認
  (ドキュメントコメント内の言及1件のみ、意図的)。
- `MockGenerationDataSource`の出力が、Python版と同じ8種のInspiration Card
  全てに対応していること、および「子ども」×「持ち物」の判定順衝突が
  発生しないことを、Dartのソースコードを直接読んで確認
  (実行はできないため、Python版で既に実測済みのロジックとの1行単位の突合による確認)。
- `strict-casts`/`strict-inference`(`analysis_options.yaml`で有効化済み)に
  抵触しないよう、新規テストファイルで`dynamic`の暗黙アクセスを避け、
  全箇所に明示的な型キャストを入れた。

---

## 6. 実際に検証できていないこと

| 項目 | 状態 |
|---|---|
| 修正後の`flutter analyze` | **未検証**。新規コード(約9ファイル)が`strict-casts`/`strict-inference`を含む既存ルールに違反していないか、CEO環境での実行でしか確定しない |
| 修正後の`flutter test`(既存7件+新規23件=30件) | **未検証** |
| Chrome上での実際の操作(Home→Confirm→Mock生成→Renderer) | **未検証**。3章・4章の構成図・シーケンス図は設計・コードからの説明であり、実機での目視確認ではない |
| MOCK/LIVE Badgeの見た目 | **未検証**。`Banner`ウィジェットの標準的な使い方に従ったが、実際の表示位置・視認性は確認できていない |
| `--dart-define=FORGE_MOCK_MODE=false`でのLive Mode切り替え | **未検証** |

---

## 7. CEO再検証手順

```powershell
cd frontend
flutter clean
flutter pub get
flutter analyze
flutter test --reporter expanded
flutter run -d chrome
```

Chrome起動後:
1. 画面右上に`MOCK`のBadgeが出ていることを確認。
2. Home画面でInspiration Card(例: 🛒買い物)をタップ→「これで作る」をタップ。
3. Confirm画面で「この内容で作ります」をタップ。
4. 生成中、AppBar付きのローディング画面が一瞬表示され(戻るボタンが押せる状態)、
   その後チェックリスト画面(Renderer描画)に遷移することを確認。
5. チェックリストにアイテムを追加・チェック・削除できることを確認
   (Runtime自体はFORGE-MERGE-001〜005で変更していないため、
   基本動作は従来通りのはず)。
6. エラー画面が出ないこと(Mock Modeでは構造上出ないはずだが、実機確認が最終判断)。

`flutter analyze`が`No issues found!`、`flutter test`が`All tests passed!`
(30件)となれば、今回の変更が意図通りであったことが確認できる。
Live Modeも試す場合は、Backend起動後に
`flutter run -d chrome --dart-define=FORGE_MOCK_MODE=false`。
