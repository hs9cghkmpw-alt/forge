# Forge

> **話すだけで、自分専用アプリを作れるAIプラットフォーム**

Forgeは、ユーザーが自然言語で要望を伝えるだけで、AIがアプリのUI/ロジックを
**JSON定義**として生成し、Flutterクライアントがそれをその場で画面として
レンダリングする「トークネイティブ・アプリビルダー」です。

AIはコードを書きません。AIが返すのはJSONだけです。
Flutterはその JSON を解釈して動的にウィジェットツリーを組み立てます。

---

## 1. プロジェクト概要

| 項目 | 内容 |
|---|---|
| コンセプト | 会話 → JSON UI Schema → 動的レンダリング |
| 対象 | 個人が自分専用の小規模アプリを即座に作れること |
| AIの役割 | JSON UI定義の生成・修正のみ（コード生成はしない） |
| クライアントの役割 | JSON schemaを解釈し、Widgetツリーとして描画 |
| 現フェーズ | **Runtime検証フェーズ**(Mock Modeで会話→JSON UI→画面描画までEnd-to-Endに動作。CEO実機で`flutter analyze`/`flutter test`/Chrome確認済み。Language v1.1で12 Widget・Template System・AI Foundation設計まで拡張。認証・実AI・CRUDは未実装) |

将来的に以下を追加予定（現段階ではフォルダ設計のみ対応、実装はしない）:

- **Marketplace**（ユーザーが作ったアプリ/テンプレートの共有・売買）
- **Plugin**（サードパーティ機能拡張。`PluginRouter`のインターフェース設計のみ完了）
- **AI Memory**（ユーザーごとの会話・アプリ生成履歴の記憶。`Memory`のインターフェース設計のみ完了）
- **AI Improve**（生成されたアプリをAIが自動改善提案）
- **Team**（複数人での共同編集・組織管理）

Templateは`docs/spec/TEMPLATE_SPEC.md`の通り実装済み（Checklist/Memo/Form）。

---

## 2. 使用技術

### Frontend
- Flutter (Material 3)
- Riverpod（状態管理 / DI）
- Clean Architecture + Feature First
- Repository Pattern

### Backend
- FastAPI (Python)
- レイヤードアーキテクチャ（routers / services / repositories / models / schemas）

### Database / Infra
- Supabase（Postgres, Auth, Storage, Realtime）
- GitHub（ソース管理 / CI/CD）

---

## 3. セットアップ方法

### Frontend (Flutter) — Mock Mode(既定・Backend不要)

CEO環境で実測済み(2026-07-11、Flutter 3.44.5 / Dart 3.12.2 / Windows 10)。
FORGE-MILESTONE-002.2で`frontend/web/`一式を追加したため、**`flutter build web`は
`flutter create`無しでそのまま実行できるはず**(Claude環境では未検証、
`docs/development/FLUTTER_VALIDATION.md`参照)。Windows等それ以外の
プラットフォームはまだ`flutter create`を通していない。

```powershell
cd frontend
flutter clean
flutter pub get
flutter analyze
flutter test
flutter run -d chrome
flutter build web --debug
```

Mock Modeが既定(`AppConfig.mockMode`の初期値`true`)のため、Backendを
起動していなくても「これで作る」→確認→生成、まで一通り操作できる
(実際のAIではなく、決定的なMock Generatorがその場でJSON UI Schemaを
作る。画面右上に`MOCK`の小さなBadgeが出る)。

### Frontend (Flutter) — Live(HTTP) Mode

BackendのAPIを実際に呼びたい場合は、Backend起動後に以下で実行する。

```powershell
flutter run -d chrome --dart-define=FORGE_MOCK_MODE=false
```

画面右上のBadgeが`LIVE`になる。Backendが起動していない/接続できない場合は
「接続できませんでした」という簡潔なエラー画面が表示される
(開発者向けの詳細はログにのみ出力される)。

### 標準検証スクリプト(FORGE-MILESTONE-003.1で追加)

**運用方針(FORGE-MILESTONE-004より)**: 「Pythonだけ変更した」
「Flutterだけ変更した」という区別に関わらず、**毎回`scripts/verify.ps1`
(Python Test + flutter analyze + flutter test + flutter build web)を
CEO環境で実行し、通過したことをもってそのマイルストーンの完了とする。**
Claude側が「今回はFlutterを変更していないので再検証不要」といった
判断を行うことはしない(DECISIONS.md D55参照)。

毎回`flutter clean`〜`flutter build web`を手動で1つずつ実行する手間を
減らすため、`scripts/verify.ps1`(Windows PowerShell 5.1対応)を用意した。

```powershell
cd forge   # Repository Root
.\scripts\verify.ps1              # Python Test + flutter clean/pub get/analyze/test/build web
.\scripts\verify.ps1 -RunChrome   # 上記に加えて flutter run -d chrome も実行
.\scripts\verify.ps1 -SkipPython  # Python環境が無い場合、Flutter系のみ実行
.\scripts\verify.ps1 -SkipBuild   # 高速確認したい場合、build webを省略
```

PowerShellスクリプトの直接実行がブロックされる環境では、代わりに
`scripts\verify.bat`をダブルクリックする(実行ポリシーをこのプロセス内だけ
一時的に緩和して`verify.ps1`を呼び出す)。

途中のステップが失敗してもスクリプト全体は止まらず、最後に全ステップの
成功/失敗サマリーを表示する。ログは`verify_logs/`配下へ実行のたびに
タイムスタンプ付きファイル名で保存される(過去ログを上書きしない)。

**文字コードについて(FORGE-MILESTONE-003.2で確定)**: `scripts/verify.ps1`は
UTF-8(BOM付き)で保存されており、内容は英数字のみ(日本語のコメント・
メッセージを含まない)。これは意図的な設計である。

CEO実機で、`verify.ps1`の日本語部分が文字化けし(例: 「サマリー」が
「縺ｵ縺ｾ繝ｪ繝ｼ」のような文字列になる)、PowerShellが構文エラー
(閉じ引用符・閉じ括弧・catchが無い)として起動できない事象が発生した。
実際にファイルのバイト列を検査し、以下を確定した(推測ではない)。

- ファイルの実体はBOM無しの正しいUTF-8だった(バイト列を検証し、正しく
  UTF-8としてデコードできることを確認済み)。
- Windows PowerShell 5.1は、BOMが無い`.ps1`ファイルをUTF-8と決め打ちせず、
  システムのANSIコードページ(日本語Windowsでは既定でShift_JIS/CP932)で
  読み込む仕様である。この結果、UTF-8の日本語部分がShift_JISとして
  誤読され、文字化けした。
- 実際にUTF-8の日本語バイト列をShift_JISとしてデコードし直したところ、
  CEOが報告した文字化けと同じ系統の文字列("繧"含む文字化け)が
  再現できた。

対応として、`verify.ps1`本体からJapanese文字を排し、メッセージは
`VERIFY START`のような英数字のみにした上で、UTF-8 BOM付きで保存する
(BOMがあれば、PowerShell 5.1でもUTF-8と正しく認識される)、という
二重の対策を行った。

**注記**: このスクリプト自体はClaude環境(Flutter SDK・PowerShellが無い)では
一度も実行できていない。CEO環境での実行結果が最初の実測になる。


```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Database (Supabase)
```bash
cd database
# supabase CLI を利用したマイグレーション適用（今後追加）
supabase db push
```

### 環境変数
`.env.example` を各ディレクトリに用意し、`.env` にコピーして値を設定する運用を想定
（Supabase URL / anon key / service role key / OpenAI or Anthropic API key 等）。

---

## 4. ディレクトリ構成と役割

```
forge/
├── frontend/        # Flutterアプリ（Clean Architecture / Feature First）
│   └── lib/
│       ├── core/        # DI・theme・network等、全feature共通の基盤
│       ├── shared/       # feature横断のロジック（UIを持たない。shared_widgetsとは別）
│       ├── plugins/      # プラグインを受け入れる契約（interfaces/registry）
│       ├── json_ui/      # JSON→Widget動的レンダリングエンジン（Forgeの中核）
│       └── features/     # Feature First（_template_feature/がひな形）
├── backend/          # FastAPIサーバー（レイヤード + Clean Architecture）
│   └── app/
│       ├── core/         # 設定・DI・セキュリティ等の基盤
│       ├── domain/       # ★entities / repositories(interface) / usecases
│       ├── ai/            # AI生成・検証・記憶（JSONのみを扱う）
│       ├── plugins/       # プラグインを受け入れる契約
│       ├── services/      # 複数usecaseを跨ぐアプリケーション層
│       ├── repositories/   # domainのrepository interfaceの実装（infrastructure）
│       └── models/ schemas/ routers/ middleware/
├── shared/            # FE/BE共通のJSON Schema・定数・型定義
├── database/          # Supabaseマイグレーション・シード・RLSポリシー
├── api/               # OpenAPI仕様など、API契約の単一情報源
├── docs/              # 設計ドキュメント一式
│   ├── prompts/         # プロンプト設計の意図・変更理由（本文は置かない）
│   └── tasks/            # 依頼タスクごとの変更履歴（Task001, Task002, ...）
├── PROMPTS/           # AIが実行時に読み込むプロンプト本文（実行資産）
├── .ai/               # AI開発エージェント共通のプロジェクトコンテキスト
├── .agents/           # 役割別AI開発エージェントの定義（プレースホルダー）
├── tests/             # E2E・統合テスト（FE/BE横断）
└── .github/           # CI/CD・Issueテンプレート
```

詳細な役割は各ディレクトリ配下の `README.md` および `docs/ARCHITECTURE.md` を参照してください。
`PROMPTS/` と `docs/prompts/`、`.ai/` と `.agents/` はそれぞれ役割が異なるため、
両方に同じような名前が出てきても混同しないよう `docs/ARCHITECTURE.md` の該当セクションで区別しています。

---

## 5. ドキュメント一覧

| ドキュメント | 内容 |
|---|---|
| [docs/README.md](./docs/README.md) | ドキュメント全体の入口・読む順番 |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | アーキテクチャ全体設計 |
| [docs/spec/LANGUAGE_SPEC.md](./docs/spec/LANGUAGE_SPEC.md) | Forge Language(v1.0/v1.1)の全Widget/Action/State一覧 |
| [docs/spec/LANGUAGE_FREEZE.md](./docs/spec/LANGUAGE_FREEZE.md) | Languageのバージョニング方針 |
| [docs/spec/RUNTIME_SPEC.md](./docs/spec/RUNTIME_SPEC.md) | Runtime(Renderer/Widget Registry)のアーキテクチャ |
| [docs/spec/TEMPLATE_SPEC.md](./docs/spec/TEMPLATE_SPEC.md) | Template System(Checklist/Memo/Form)の設計 |
| [docs/spec/AI_SPEC.md](./docs/spec/AI_SPEC.md) | AI Foundation(設計のみ・未実装)の設計 |
| [docs/spec/MOCK_GENERATOR_CONTRACT.md](./docs/spec/MOCK_GENERATOR_CONTRACT.md) | Mock Generator Python版/Dart版の互換性契約 |
| [docs/API.md](./docs/API.md) | API設計方針・命名規則・バージョニング |
| [docs/DATABASE.md](./docs/DATABASE.md) | Supabaseスキーマ設計方針 |
| [docs/AI.md](./docs/AI.md) | AI ↔ JSON UI Schema の設計方針 |
| [docs/ROADMAP.md](./docs/ROADMAP.md) | 今後の開発ロードマップ |
| [docs/development/FLUTTER_VALIDATION.md](./docs/development/FLUTTER_VALIDATION.md) | Flutter検証環境・既知の注意事項 |
| [docs/reports/](./docs/reports/) | 各マイルストーンの実施レポート(FORGE-MERGE-001〜、FORGE-RUNTIME-001〜) |
| [docs/prompts/](./docs/prompts/) | プロンプト設計の意図・変更理由（本文は`PROMPTS/`） |
| [docs/tasks/](./docs/tasks/) | 依頼タスクごとの変更履歴（Task001, Task002, ...） |

---

## 6. 現フェーズで「やらないこと」

このリポジトリの現状は **Runtime検証フェーズ** です。以下は意図的に未実装です。

- ログイン・認証フロー
- **本物のAI**によるJSON生成ロジック（現在はキーワード判定による決定的な
  Mock Generatorのみ。`docs/DECISIONS.md` D8・`docs/development/
  FLUTTER_VALIDATION.md`「Mock Mode / Live Mode」参照）
- CRUD API実装
- 実際のアプリ機能画面

これらは `docs/ROADMAP.md` に定義されたフェーズに沿って、
この土台の上に追加されていきます。
