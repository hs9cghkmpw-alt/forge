# Task016 — FORGE-MILESTONE-003.1: Runtime State Contract Fix & Final Quality Closure

## 依頼内容
CEO実機でChrome起動・8カテゴリの生成成功を確認した一方、家計簿カテゴリの
追加操作で`add_item_failed`というRuntime Errorが実機発生したことを受け、
根本原因の特定・修正(PHASE1/2)、全12カテゴリのAction契約監査(PHASE3)、
Validator強化(PHASE4)、Dart/Python双方のテスト追加(PHASE5/6)、
Analyzer状況確認(PHASE7)、Web警告整理(PHASE8)、フォント方針(PHASE9)、
計算アプリ入力の扱い明確化(PHASE10)、Native AI状態の正確な記録(PHASE11)、
検証スクリプト追加(PHASE12)を依頼された。

## 行った変更
- 実際に家計簿カテゴリの生成JSONをPython Mock Generatorで取得し、
  Validatorで合格することを確認(JSON自体は正しいと確定)。
- `ForgeStateStore.addChecklistItem()`の戻り値を`bool`から
  `AddChecklistItemOutcome`(4値enum)へ変更し、正常操作(空入力)と
  契約違反を明確に分離。
- `backend/tests/test_all_categories_action_contract.py`新規
  (全12カテゴリのAction参照契約をValidator非依存で検証)。
- `frontend/test/json_ui/add_item_regression_test.dart`新規。
- `web/index.html`のPHASE8警告2件を修正(mobile-web-app-capable追加、
  viewport明示削除)。lifecycle channel警告は対応不可と判断・記録。
- `TECH_DEBT.md` TD18(Font)・TD19(Calculator fallback)追加。
- `scripts/verify.ps1`・`verify.bat`新規。
- `docs/spec/NATIVE_AI_ROADMAP.md`へ、今回のCEO実機確認がMock Modeで
  あることの明示的な確認セクションを追加。

## 変更理由
`add_item_failed`は生成JSON側の契約違反ではなく、Dart Runtime側が
「エラー」と「正常な空入力」を区別していなかったことが原因と判明した
(D48)。特定カテゴリの条件分岐ではなく、add_itemの一般契約として修正した。
