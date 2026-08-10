# Task029 — FORGE-MILESTONE-005 実物監査(3回目)対応

## 依頼内容
CEOがCEO環境で`python -m unittest discover -s backend/tests`を実行した
結果、`Ran 265 tests / FAILED (failures=2)`だった。失敗した2件
(`test_unsupported_engine_returns_error_envelope`・
`test_unregistered_provider_returns_provider_error`)は、前回追加した
Engine/Provider許可リスト化(Fix 1)導入前の古い期待値のままだったため
と特定され、テスト名・期待値・コメントのみを新しい公開HTTP契約に
合わせて修正するよう依頼された。また、レポート内の古い件数表記
(255 tests・HTTP 9件)を最終版の件数(Backend 265・HTTP 17・
Forge AI 80)へ統一するよう依頼された。

## 行ったこと
- 2つの失敗テストを、Pydantic入力層での許可リスト拒否という実際の
  経路に合わせて改名・期待値修正した。
- 契約を明文化: 「未知のengine/provider文字列 → request_error/
  schema_invalid/422」「既知だが未実装のprovider → provider_error/
  unavailable/503」。
- `test_unimplemented_provider_returns_provider_error`を、
  status_code・sub_reasonまで明示的に検証するよう強化した。
- `FORGE-MILESTONE-005-report.md`を、統一された最終件数
  (Backend 265・HTTP 17・Forge AI 80)で全面的に書き直した。
- `python -m unittest discover`(backend/forge_ai)・
  `python -m compileall backend forge_ai`を再実行し、結果を確認した。

## 変更理由
コード本体(schemas/ai.py・routers/ai.py等)の実際の挙動(Engine/Provider
許可リスト化)は正しく、CEOも「前回の3点修正はコードへ正しく反映されて
いる」と確認済みだった。問題は、この挙動変化に伴って一部の既存テストの
期待値が古いまま取り残されていたことであり、コードではなくテストの
修正が必要だった。
