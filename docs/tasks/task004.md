# Task004 — FORGE-MERGE-002: Foundation Hardening & Runtime Validation

## 依頼内容
- 新機能追加ではなく、Foundationの品質保証・長期安定化を行う。
- Flutter環境での`flutter analyze`/`flutter test`実行(Task 1)。
- 分析結果に基づくRuntime修正(Task 2)。
- Renderer公開APIの一覧化と互換性ポリシー(Task 3)。
- Validatorを26テストから80件以上へ拡張(Task 4)。
- Language Freeze方針の文書化(Task 5)。
- Runtime Architectureの自己レビュー(Task 6)。
- Foundation全体の監査、AI Compiler搭載時の破綻可能性の確認(Task 7)。
- ドキュメント同期(Task 8)。
- 新規Widget・新規Language・Backend追加・AI機能追加・UI変更・新画面・
  Supabase・FastAPI追加は禁止。

## 行った変更

### Task 1(未達成。事実として明記)
Claudeのサンドボックスには引き続きFlutter/Dart SDKが無く、ネットワークも無いため、
`flutter analyze`・`flutter test`は実行できなかった。CEO環境での実行が必須。

### Task 2(代替実施: 手動ハードニングレビュー)
実際のanalyze結果が無いため「Task 2そのもの」ではなく、Dart/Flutterのベストプラクティスに
基づく手動レビューを実施し、2件を修正した。
- `json_ui/renderer/forge_renderer.dart`: 定数化できる箇所への`const`付与漏れを1件修正。
- `json_ui/widget_registry/widget_registry.dart`: `_buildRow`が全childrenを一律`Expanded`で
  包んでおり、button等がPrototype本来の見た目より横に引き伸ばされる不具合を修正
  (text_fieldのみExpandedにする形へ変更)。

### Task 3
`docs/spec/RENDERER_API.md` を新設。依頼された6概念(Registry/Renderer/RenderContext/
RenderNode/Widget Factory/Widget Mapper)のうち3つ(RenderContext/Widget Factory/
Widget Mapper)は独立クラスとして存在しないことを明記した上で、実際のAPI一覧・
Public/Internal/Experimental分類・互換性ポリシーを作成。

### Task 4
`backend/tests/test_schema_validator_extended.py` を新設(71件)。既存19件
(test_schema_validator.py)+ 71件 + Mock Generator側7件 = **合計97件**、
Claude環境で`python -m unittest`実行の上、全件合格を確認済み。Unknown Widget/
Unknown Property/Missing Property/Invalid Type/Enum Error/Version Error/
Duplicate ID/Deep Tree/Circular Reference/Null/Array Error/Object Error/
Action Error/Migration Errorの14カテゴリ+正常系境界値を網羅。テスト作成の過程で
2件の既知のギャップ(checklist item IDの重複が未検出、string_list型を使うWidgetが無い)
を発見し、TECH_DEBT.mdへ記録した(いずれもWidget追加禁止のため今回は未対応)。

### Task 5
`docs/spec/LANGUAGE_FREEZE.md` を新設。Freeze条件・Breaking/Minor/Patchの定義・
Migration・Deprecation・Backward Compatibilityを規定。**v1はまだFreeze宣言できる
状態ではない**(Runtime未検証のため)ことを明記した。

### Task 6・Task 7
新規ファイルは作らず、統合レポート(`FORGE-MERGE-002-report.md`)の該当章に
自己レビュー結果をまとめた。

### Task 8
- `TECH_DEBT.md` を新設(8項目)。
- `docs/tasks/task004.md`(本ファイル)を新設。
- `CHANGELOG.md` を新設(リポジトリ直下)。
- `docs/DECISIONS.md` へD13〜D15を追記。
- `docs/ROADMAP.md` の該当箇所へ検証状況の追記。

## 変更理由
指示書の「最重要事項: 事実と推測を厳密に分離すること。実際に確認できたものだけを
『完了』とする」に従い、Task 1を「できたことにする」代わりに、できなかった事実を
明記した上で、環境制約の中で最大限価値のある代替作業(Task 4のテスト拡充、
手動コードレビューによる実バグ2件の発見・修正)に労力を振り向けた。
