# Task031 — FORGE-MILESTONE-006 実物監査(2回目)対応(4点修正)

## 依頼内容
CEOがM006成果物(main spec 954行・ADR7件・図9件・完全トレース例6件・
Task/CHANGELOG)を実物監査し、Hybrid方式・Decision Trace・Cognitive
RevisionとSchema Repairの分離・M004/M005責務境界は承認した上で、正式
確定前に以下4点の文書修正を求めた。新規コードは追加しないこと。

1. Cognitive Pipelineの段階数不一致(「全16段階」の記載に対し個別定義が
   14段階)の解消。
2. Domain confidence<0.5でHIGH確認とする基準(4.3節)と、confidence
   0.3〜0.5未満でGenericへフォールバックする基準(14.2節)の矛盾解消。
3. Ambiguity Detection自体が失敗した場合に「曖昧さ無し」として楽観的に
   継続する設計の廃止。
4. Application PlanningがTemplate Selectionの`recommended_patterns`を
   先取りして参照する、隠れた循環依存の解消(Preliminary/Final二段階化)。

## 行ったこと
- 3章へ「Cognitive Revision」「Human Confirmation / Escalation」を
  独立段階として追加し、Design Critic以降の並びを実質16段階へ統一した。
- 4.3節・14.2節を、Privacy/Safety/Permission関連HIGH ambiguityを
  最優先とする3段階の優先順位へ統一し、旧来の2閾値(0.3/0.5)を
  0.5/0.8の2閾値へ整理した。
- 4.4節を新設し、Ambiguity Detection失敗時に`detection_status=
  "failed"`/`overall_severity="unknown"`を明示し、Domain種別に応じて
  確認/安全停止と限定継続を分岐させる設計へ変更した。
- 3.8節・3.9節を改訂し、Application Planningの内部フェーズとして
  Preliminary Pattern Candidatesを新設、Template SelectionをFinal
  Template Selectionとして再定義した。ADR-008を新設し、Preliminary/
  Final不一致時の再計画がCognitive Revisionとカウンタを共有すること
  (二重ループ防止の第3の適用例)を記録した。
- 図1(Cognitive Pipeline)・ADR-007・`docs/examples/
  05_welfare_support_record.md`等、影響する図・ADR・例を更新した。
- 本セッションでの独立監査により、ADR新設(7→8件)に伴う0章・21章の
  表記漏れを発見・修正した。
- Python全テスト(backend 265件・forge_ai 80件)を再実行し無影響を確認、
  `backend/app/ai/native/`・Flutterの無変更を確認した。

## 変更理由
本Taskは設計文書の修正であり、コードの「変更理由」に相当する記録は
無い。各修正の設計上の理由は、本体の該当節(「CEO監査により...」と
明記した箇所)およびADR-007・ADR-008に記録した。
