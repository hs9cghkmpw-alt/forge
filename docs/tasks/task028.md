# Task028 — FORGE-MILESTONE-005 実物監査(2回目)対応

## 依頼内容
CEOがHTTP層を含めて実機検証(Backend 255/255・HTTP 9/9・forge_ai
80/80・Python compile PASS)した上で、正式完了前に3点の修正
(Engine/Providerの許可リスト化、Plan変換の情報消失修正、
max_repair_attemptsの上限を2回へ)と、軽微な修正1点(prompt_pipeline.py
冒頭の実コードと矛盾するdocstring)を依頼された。

## 行ったこと
1. `GenerationOptionsDTO`の`engine`/`provider`を`Literal`型へ変更し、
   HTTP公開API経由では`native`/`local`/Provider名としての`forge_ai`を
   受理しないようにした。
2. `plan_ir_from_application_plan()`の戻り値を`PlanConversionResult`
   (`plan_ir`+`warnings`)へ変更し、以前は捨てていた変換警告を
   `Diagnostics.conversion_warnings`経由でHTTPレスポンスまで
   到達させた。
3. `max_repair_attempts`の上限を`le=10`から`le=2`へ修正し、境界
   (0/1/2は許可、3以上は422)のテストを追加した。
4. `prompt_pipeline.py`・`forge_ai_adapter.py`冒頭の、実コードと
   矛盾していたdocstringを修正した。

## 変更理由
CEOの実物監査により、公開契約(HTTP API)がRouter内部の後方互換用
エイリアスをそのまま公開してしまっている、変換時の警告情報が
どこにも返されていない、Repair上限のHTTP側チェックが契約と矛盾する
上限になっている、という3点の実装ミスが発見されたため。
