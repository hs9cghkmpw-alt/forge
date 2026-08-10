# Task030 — FORGE-MILESTONE-006: Cognitive Architecture v2.0 設計

## 依頼内容
「M006で扱う『Forgeがどう考えるか』を、実装前に設計・固定する」ことを
目的とした、Architecture Design Onlyの依頼を受けた。Cognitive Pipeline
(16段階)・Domain/World/Meaning Model・Requirement Extraction・Planner・
Template Selection・Design Critic・Self-Revision Loop・LLM使用方針・
Confidence Model・Decision Trace・Learning-Ready Design・Failure Modes
(14種)・M004/M005責務境界・3方式比較(Rule-Based/LLM中心/Hybrid)・
図(9種)・完全トレース例(6件)・ADR(7件)の作成が求められた。新規
Python/Dartコードの追加、既存コードの変更はいずれも禁止された。

## 行ったこと
- `docs/spec/FORGE_COGNITIVE_ARCHITECTURE_V2.md`(新規、約960行)を
  作成し、依頼された設計項目をすべて記述した。
- `docs/adr/`へADR 7件を作成した。
- `docs/diagrams/`へMermaid図9件を作成した。
- `docs/examples/`へ完全トレース例6件(買い物リスト・家計簿・日記・
  満足度アンケート・福祉支援記録・病院予約)を作成した。うち福祉支援
  記録は、Privacy起因のHIGH Ambiguityによりパイプラインが
  Application Plan生成前に停止し、ユーザー確認を要求するケースとして
  意図的に選定した。
- 既存のforge_ai/(M004)実装(Domain/World/Intent/Planner/Compiler/
  RepairEngine/QualityEngine)と、本設計の対応関係・差分(例: World
  Modelへの Events/States/Permissions追加)を明記した。
- Python/Dart全テストを再実行し、無影響であることを確認した。

## 変更理由
本Taskは実装ではなく設計であるため、コードの「変更理由」に相当する
記録は無い。設計上の主要な判断理由は、`docs/adr/`の各ADR
(Context/Decision/Alternatives/Consequences/Revisit Conditions)に
記録した。
