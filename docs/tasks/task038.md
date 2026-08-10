# Task038 — FORGE-MILESTONE-007 Phase 1.1(残修正)実物監査対応

## 依頼内容
CEOがForge AI 156件・Backend 265件の全合格を確認し、Provider契約・
Confidence分離・Validation UX・Criticカバレッジ・Template tie-breakの
方向性を承認した上で、Meaning Model・複数画面化へ進む前の残修正4点を
求めた。

1. Preliminary/Final不一致判定の責務をTemplateSelectorへ集約する。
2. Template Selection・Critic・RevisionをDecision Traceへ記録する。
3. Functional/Data/Validation Requirementの割当判定を実データに
   基づかせる(target_ref/operation_refの導入含む)。
4. Design CriticのDocstring・実装・レポートにおけるPrivacy/
   Accessibilityの扱いを統一する。

## 行ったこと
- 4点それぞれについて、実際のコード・テストを読み、実行して独立に
  監査した。結果、4点とも既に正しく実装・テスト済みであることを
  確認した(差し戻しは無かった)。
- 監査の過程で、Cognitive Revisionループ内に`design_critic.evaluate()`
  の冗長な2重呼び出しを発見し、削除した。
- CEO指定6例を実際に実行し、Domain/Template判定・release_ready=True
  の維持と、Decision Trace件数の増加(2件→5件)を確認した。
- Forge AI全テスト(164件)・Backend全テスト(265件)を実行し、
  無影響を確認した。`backend/app/ai/native/`・Flutterの無変更も
  確認した。

## 変更理由
本Taskは主に監査であり、実質的な設計変更は行っていない。発見した
冗長コードの削除は、動作結果に影響を与えない、コードの明瞭性向上を
目的とした軽微な修正である。
