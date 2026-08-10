# Task036 — FORGE-MILESTONE-007 第一段階実装: Cognitive Pipeline最小実装

## 依頼内容
`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` v1.3を正式な実装契約
とし、既存`run_pipeline()`を壊さず、簡単な自然言語(買い物リスト・
タスク管理・日記・アンケート・予定・在庫の6例)から実用的なアプリ構造を
生成できる最小のCognitive Pipelineを、動作確認可能な形で実装することを
依頼された。Legacy/Cognitive Protocolの分離・Boolean Feature Flag不使用・
NotImplementedErrorの非捕捉・revision_attemptカウンタ共有等、過去4回の
監査で確定した原則の厳守が求められた。

## 行ったこと
- 作業開始時点でforge_ai既存80テストのうち3件が失敗していることを
  発見し、原因(Domain定義の追加漏れ)を特定・修正した(最優先対応)。
- Blueprint v1.3 Task1〜9に基づき、Cognitive型・Protocol・Context・
  Dependencies・Outcomes・Error Model・11個の実装モジュール・
  Orchestrator・Facadeを実装した。
- CEO指定6例全てで、実際にパイプラインを実行し、正しいDomain判定・
  Template選択・Application Plan生成・Critic合格・Quality評価まで
  到達することを確認した。
- Unit/Integration/Golden Testを56件新規追加し、既存80テストとの
  合計139件が全合格することを確認した。
- Backend 265件・Native・Flutterへの影響が無いことを確認した。

## 変更理由
CEOの明示的な依頼(Blueprint v1.3の実装)に基づく。既存コードへの
変更(Intent/World/ApplicationPlan/ScreenPlanの拡張)は、いずれも
既定値付きフィールド追加による後方互換な拡張であり、既存の呼び出し
コード・テストには影響しない設計とした。Domain定義の追加漏れ修正は、
既存テストの回帰を防ぐための必須対応だった。
