# Task032 — FORGE-MILESTONE-007 PREPARATION: Implementation Blueprint

## 依頼内容
M006(Cognitive Architecture v2.0)が承認済みであることを前提に、実装
(M007)では「設計しながら実装」ではなく「設計どおりに実装するだけ」の
状態にするための、実装可能な設計書(Implementation Blueprint)の作成を
依頼された。対象はディレクトリ構成・Cognitive Context・Pipeline
Orchestrator・Interface(Protocol)設計・依存関係規則・Error Model・
テスト戦略・実装順序・既存M004からのMigration Planの9タスク。新規
Python/Dart/Flutterコードの追加は禁止された。

## 行ったこと
- `docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md`を新規作成し、
  依頼された9タスクを全て記述した。
- 既存`forge_ai/core/`の7ファイルを一切移動せず、新規7サブディレクトリ
  (input_processing/understanding/planning/critic/confirmation/
  orchestration)へM006の新規認知能力を追加する構成を設計した。
- Cognitive Context(Immutable、`with_*`更新方針)・Pipeline
  Orchestrator(唯一の制御点)・新規/既存流用Protocol・依存規則
  (禁止importの明示)・Cognitive Error階層(M005 pipeline_errors.py
  との名前衝突の扱いを含む)・テスト件数概算(約171〜203件)・実装順序・
  Feature Flag方式のMigration Planを設計した。
- `docs/diagrams/10_m007_dependency_graph.md`(依存図、禁止import例を
  含む)を新規作成した。
- Python全テスト(backend 265件・forge_ai 80件)を再実行し無影響を
  確認、`backend/app/ai/native/`・Flutterの無変更を確認した。

## 変更理由
本Taskは実装ではなく設計であるため、コードの「変更理由」に相当する
記録は無い。設計上の主要な判断(既存ファイル非移動・Feature Flag
方式・Error階層の名前衝突扱い等)の理由は、本体の該当節に記録した。
