# Task033 — FORGE-MILESTONE-007 PREPARATION 実物監査対応(4点修正)

## 依頼内容
CEOが`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md`を実コードと
突き合わせて監査し、ディレクトリ構成・Immutable Context・単一
Orchestrator・依存規則・段階Migration・テスト方針は承認の上、実装
開始前に以下4点の文書修正を求めた。新規コードは追加しないこと。

1. `needs_confirmation`を既存`PipelineResult`へダミー値経由で変換
   する設計の撤回、Facade分離方式(`run_cognitive_pipeline()`+
   `CognitivePipelineOutcome`)への変更。
2. 既存Protocolのメソッド名(`build`/`plan`/`resolve_from_keywords`等)
   とOrchestrator疑似コードの統一(架空の`process(context)`統一規約の
   撤回)。
3. Initial Quality(M004)/Final Quality(M005)の責務確定。
4. 未捕捉Cognitive ErrorがM005で実際にどう分類されるか(既存
   `except NotImplementedError`/`except Exception`の実装に基づく訂正)。

## 行ったこと
- Task9を全面書き換えし、`run_pipeline()`を無変更のまま維持しつつ、
  `run_cognitive_pipeline() -> CognitivePipelineOutcome`という新
  Facadeを設計した。`CognitivePipelineOutcome`を`Success`/
  `NeedsConfirmation`/`Failed`の3独立dataclassのUnionとして定義し、
  単一dataclassの全フィールドOptional化という代替案も検討した上で
  却下した(ADR-009新設)。
- Task2.3・Task3.2/3.3を書き直し、既存Protocolは実際のメソッド名で
  呼び、新規Context指向Protocolのみ`process(context)`規約を使う、
  という2階層の呼び出し規約を明記した。
- Task9.3を新設し、Initial Quality(M004)/Final Quality(M005、既存
  実装済み)の責務分担を明記した。
- Task6.3を訂正し、既存`prompt_pipeline.py`の実際の例外捕捉順序に
  基づく正確な対応表へ書き換えた。`ConfirmationRequired`が例外として
  Orchestrator外へ漏れない設計(主要経路は例外を使わない直接return)を
  明記した。
- 修正作業中に、既存`IntentBuilderProtocol.build(meaning, world)`の
  シグネチャとM006 3章の掲載順との実行順序の食い違いを発見し、
  Task3の疑似コードで明確化した。
- Python全テスト(backend 265件・forge_ai 80件)を再実行し無影響を
  確認、`backend/app/ai/native/`・Flutterの無変更を確認した。

## 変更理由
本Taskは設計文書の修正であり、コードの「変更理由」に相当する記録は
無い。各修正の設計上の理由は、本体の該当節およびADR-009に記録した。
