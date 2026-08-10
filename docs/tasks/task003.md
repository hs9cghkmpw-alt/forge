# Task003 — FORGE-MERGE-001: Prototype統合と最初の縦の一本

## 依頼内容
- Prototype v0.1.3(添付ZIP)とforge-foundation(添付ZIP)の両方を現物監査する
- 監査結果に基づき、統合方針・Forge Language v1・Migration Planを確定する
- 可能な範囲で実装し、最初のEnd-to-End経路(Home→Confirm→Deterministic Mock
  Generator→Forge JSON→Validator→Flutter JSON UI Renderer→操作可能な
  チェックリスト)を通す
- 実行できたテストと実行できなかったテストを明確に区別する

## 行った変更

### 監査
- 両ZIPを全ファイル展開し、`.gitkeep`のみのプレースホルダー(49件)と
  実コード(Dart 1ファイル・Python 1ファイル)を区別した。
- 先行して提示されていた「forge-foundationに13件のValidatorテスト・
  19件のチェックが既に合格している」という趣旨の記述は、現物には
  一致する痕跡が無いことを確認した(統合レポート Repository Audit /
  Conflict Report参照)。

### Forge Language v1
- `shared/schemas/ui_schema.v1.json` をドラフト(`screen: object`のみ)から
  正式なv1(6 Widget種別・4 Action種別・4 State型、additionalProperties:false、
  再帰深度/配列長の上限つき)へ更新した。

### Validator
- `backend/app/ai/validators/schema_validator.py` を新設(構文/Schema/意味/
  Runtime Safetyの4層、エラー形式は`path/category/severity/rule/message`)。
- `backend/tests/test_schema_validator.py` を新設。19ケースをClaudeの環境で
  `python -m unittest` により実行し、19/19合格を確認済み。

### Mock Generator
- `backend/app/ai/generators/mock_generator.py` を新設。Prototypeの
  `generateToolFrom`のキーワード判定を引き継ぎつつ、出力をForge JSONへ変更。
  Inspiration Cards 8種類全てに対応するようカテゴリを3→8へ拡張した
  (監査で発見したギャップの修正。DECISIONS.md D10参照)。
- `backend/tests/test_mock_generator.py` を新設。7ケース+8カテゴリ全件の
  Validator突合テストを含め、Claudeの環境で26/26(Validatorと合算)合格を確認済み。

### Backend配線
- `backend/app/schemas/ai.py`・`backend/app/routers/ai.py` を新設し、
  `POST /api/v1/ai/generate` を実装。`backend/app/main.py` にrouterを追加。
- これらはfastapi/pydanticに依存するが、Claudeのサンドボックスには
  ネットワークが無く両パッケージを導入できなかったため、Claude自身は
  実行・importテストをしていない(`py_compile`による構文チェックのみ実施・合格)。

### Frontend(Runtime)
- `frontend/lib/json_ui/schema/forge_document.dart`(モデル)、
  `widget_registry/widget_registry.dart`(Registry+6種類のWidget実装+
  Fallback)、`renderer/forge_renderer.dart`・`forge_runtime_state.dart`
  (画面描画・状態管理・画面遷移)を新設。
- freezed/json_serializable/riverpod_generatorは使わず手書きにした
  (DECISIONS.md D5)。go_routerも使わず素のNavigatorにした(D6)。
- Dart/Flutter SDKがClaudeのサンドボックスに無いため、`flutter analyze`・
  `flutter test`・`flutter run`はいずれも未実施。相対importの解決(23件)と
  カスタム型名の定義-参照突合は機械チェック済み(Implementation Report参照)。
  レビュー中に2件の実装ミス(未定義メソッド呼び出し、switch文のフォールスルー)を
  発見し修正済みだが、これは「Dart側は`flutter analyze`を実際に通すまで
  信用しないこと」の裏付けでもある。

### Frontend(Prototype UX移植)
- `core/theme/forge_theme.dart`(Prototypeの`ForgeTheme`をそのまま移植)。
- `features/app_generation/` 配下にdomain/data/presentationの3層を新設し、
  HomeScreen・ConfirmScreenを移植。
  - ConfirmScreenの古い音声入力言及コメントを削除(監査で発見。DECISIONS.md/
    統合レポートConflict Report参照)。
  - ToolScreenは`GeneratedAppScreen`へ置き換え、Forge JSONをRendererに
    渡す形にした(ToolScreen自体は削除・移植しない。Widget構成の知識は
    すべてRuntime側に移した)。
- `main.dart`を、プレースホルダー画面からHomeScreen起動へ更新。

### ドキュメント
- `docs/DECISIONS.md` を新設(12件の決定を記録)。
- `docs/ROADMAP.md` を更新(検証済み/未検証を区別して反映)。
- `docs/AI.md` のJSON例を実際のv1 Schemaの形へ更新(旧例は
  `screen`が単数・`type: screen`付きで、実装したv1と食い違っていたため)。

## 変更理由
FORGE-MERGE-001の指示に従い、「監査したので次の指示をください」で止めず、
上位(監査→方針→Language v1→Validator)が固まった時点で下位
(Renderer→UX移植→配線→テスト→ドキュメント)へ進んだ。ただし、
Dart/FastAPI実行環境がClaude側に無いという制約は日本語での言い訳ではなく
構造的な事実であるため、検証済み(Python: unittest実行で確認)と
未検証(Dart: 静的な突合チェックのみ)を明確に分けて記録した
(統合レポート Test Report / Known Issues 参照)。
