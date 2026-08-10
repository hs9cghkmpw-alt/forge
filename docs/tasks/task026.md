# Task026 — Adapter Contract v1.1(CEO実コード監査の6指摘に対応）

## 依頼内容
CEOが`docs/spec/ADAPTER_CONTRACT_V1.md`(v1.0)を実コードと突き合わせて
監査した結果、「Concrete type flow: FAIL」「Pipeline ownership: FAIL」
を含む7点の指摘を受け、6項目の修正を依頼された。新規コード実装は
禁止され、Adapter Contractの文書修正のみに限定された。

## 行ったこと
1. `forge_ai.Compiler.compile()`が`ApplicationPlan`しか受け取れないこと
   を実際にソースコードで確認し、v1.0の「段階ごとの型変換」設計を
   撤回。`forge_ai.core.pipeline.run_pipeline()`(既存)を「粗粒度
   Facade」として採用する設計へ全面変更した(1章)。
2. パイプライン所有者をM004(認知パイプライン)とM005(HTTP/Provider/
   Validator/Repair制御)に明確に分離した(1.2章)。
3. Forge IR境界を「dict型の一致」ではなく「Validator合格済みdict」
   へ訂正した(2.3章)。
4. `Intent.required_actions`の情報損失(actions_needed=()固定)を
   修正し、`PlanIR.unassigned_actions`フィールド追加の必要性を
   記録した(2.2章)。
5. `key_elements→data_needed`の無条件変換を修正し、データ実体/
   ユーザー操作/画面表現概念の3分類方針を追加した(2.2章)。
6. HTTP Contractで`engine`と`provider`を分離し、Provider既定値を
   `mock`へ修正した(4.0章・5.2章)。
7. HTTPエラーコード(400/422)の基準を統一した(3.1章)。

すべて`docs/spec/ADAPTER_CONTRACT_V1.md`の改訂(v1.0→v1.1)として行い、
新規コードは一切追加していない。

## 変更理由
CEOの実コード監査により、v1.0の設計をそのまま実装すると型エラーで
即座に停止することが判明したため。「実装開始前にAdapter Contractを
固める」という今回のマイルストーンの目的そのものが、この監査によって
初めて意味を持った(設計段階で発見できたことで、M005実装時の手戻りを
防げる)。
