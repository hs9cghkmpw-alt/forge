# FORGE-MILESTONE-005 実施レポート — Backend AI Integration Implementation

**Ref:** FORGE-MILESTONE-005(Implementation)　**担当:** Principal Engineer / Architect（Claude）
**日付:** 2026-07-14(実物監査3回を経て最終化)

Adapter Contract v1.1(`docs/spec/ADAPTER_CONTRACT_V1.md`)を正式仕様として実装した。
**設計変更は行っていない**(発見した問題はいずれも実装レベル、または
テストの期待値レベルで解決した)。

---

## 0. 最終テスト件数(統一済み)

| スイート | 件数 | 状態 |
|---|---|---|
| **Backend tests** | **265** | 248 PASS(Claude環境で実行・確認済み)+ 17 SKIP(fastapi/pydantic無し) |
| **HTTP tests**(Backend testsの内数) | **17** | CEO環境で実機実行、後述の3点修正後は未再実行(要CEO再確認) |
| **Forge AI tests** | **80** | 実行・全合格(Claude環境で実行・確認済み) |
| **Python compile**(`compileall backend forge_ai`) | — | exit code 0、エラー無し |

過去のレポート本文に残っていた古い件数(255/9件等)は本版で整理した。

---

## 1. 完成した経路

```
HTTP Request → M005(PromptPipeline) → M004 run_pipeline() → Validator
→ (不合格ならRepair) → Quality再評価 → HTTP Response
```

M005はM004の個別コンポーネント(MeaningExtractor/IntentBuilder/Planner/
Compiler)を直接呼ばない(自動テストで回帰確認済み)。

---

## 2. 実装したファイル(実装ラウンド全体を通して)

| ファイル | 内容 |
|---|---|
| `backend/app/ai/runtime/forge_ai_adapter.py` | Intent/Plan/RepairIssue/RepairResult/Quality の5 Adapter関数。`PlanConversionResult`で変換警告も返す |
| `backend/app/ai/runtime/forge_ai_provider_bridge.py` | `ForgeAIProviderBridge` |
| `backend/app/ai/foundation/providers.py` | `MockLLMAdapter`(実際に動作する唯一のProvider) |
| `backend/app/ai/foundation/interfaces.py` | `PlanIR.unassigned_actions`追加(後方互換) |
| `backend/app/ai/runtime/provider_router.py` | `mock`登録、既定値を`mock`へ |
| `backend/app/ai/runtime/pipeline_errors.py` | Error Contract 5分類+`request_error`の例外階層 |
| `backend/app/ai/runtime/prompt_pipeline.py` | Facade方式、`conversion_warnings`を`Diagnostics`へ追加 |
| `backend/app/schemas/ai.py` | Request/Response/Error Envelope。`engine`/`provider`をLiteral許可リスト化、`max_repair_attempts`上限2 |
| `backend/app/routers/ai.py` | `POST /api/v1/ai/generate` |
| `backend/app/exception_handlers.py` | 例外→Error Envelope変換 |
| `backend/app/main.py` | ハンドラ登録 |
| `scripts/verify.ps1` | `pip install -r requirements.txt`ステップ追加 |

---

## 3. 公開HTTP契約(3回の実物監査を経て確定)

| 入力 | 結果 |
|---|---|
| `engine`/`provider`が許可リスト外の文字列 | `request_error` / `schema_invalid` / **HTTP 422**(Pydantic入力層で拒否、Pipelineへ未到達) |
| `provider`が許可リスト内だが未実装(例: `openai`) | `provider_error` / `unavailable` / **HTTP 503**(Pipelineへ到達し、実際に呼んだ結果) |
| `natural_language`が空文字・フィールド欠如 | `request_error` / `schema_invalid` / **HTTP 422** |
| JSON構文自体が不正 | `request_error` / `json_syntax_invalid` / **HTTP 400** |
| `max_repair_attempts`が3以上 | `request_error` / `schema_invalid` / **HTTP 422** |
| 正常生成(Validator合格) | `status: success` / **HTTP 200** |

許可される`engine`: `"forge_ai"`のみ。許可される`provider`: `"mock"` /
`"openai"` / `"claude"` / `"gemini"` / `"oss"`。`"native"`・`"local"`・
Provider名としての`"forge_ai"`は、Router内部では後方互換のため解決可能
だが、HTTP公開APIでは受理しない。

---

## 4. 実装中に発見した問題と対応(いずれも設計変更ではない)

1. **Mock応答の型不整合**(実装中に発見): `MockLLMAdapter`が
   `"screens"`へ文字列配列を返し、`forge_ai.Planner`の期待する
   オブジェクト配列と食い違って`AttributeError`になった。forge_ai/
   既存の「空なら安全なデフォルトへフォールバックする」ロジックを
   活かし、Mock側で空配列を返すよう修正した。
2. **Repair二重ループ**(設計段階で発見、Adapter Contractで対応済み):
   `RepairEngine(bridge, max_iterations=1)`で内側ループを無効化し、
   `PromptPipeline`側のループのみがリトライ回数を制御する。
3. **HTTPテストの重複**(実装中に発見): 並行作業で作られていた
   `test_http_api.py`と自作の`test_http_ai_generate.py`がほぼ完全に
   重複していた。比較の結果`test_http_api.py`側の実装ミス(HTTP 200 vs
   422の期待値誤り)を発見・修正し、自作ファイルは統合のため削除した。
4. **公開契約とテスト期待値の不一致**(3回目の実物監査で発見):
   Fix 1(Engine/Providerの許可リスト化)導入後、既存2テストが
   「許可リスト導入前の古い経路」を期待したままになっていた。3章の
   契約に合わせて期待値・テスト名・コメントを更新した(6章で詳細)。

---

## 5. 未検証事項(正直な申告)

Claude環境にfastapi・pydanticがインストールできない(ネットワーク不可、
実際に`pip install`を試行し失敗を確認済み)ため、HTTP層
(`schemas/ai.py`・`routers/ai.py`・`exception_handlers.py`・
`main.py`・`test_http_api.py`)はClaude環境では実行できていない。

**CEOが既に2回、実際にCEO環境でHTTP層を実行し、1回目は9件、2回目は
実物監査により2件の失敗を発見済み。** 今回(3回目)の修正後、
再度CEO環境での実行確認が必要(6章の2テストの新しい期待値が正しいかを
含む)。

---

## 6. 3回目の実物監査(今回)で修正した内容

CEOがCEO環境で実行した結果、`Ran 265 tests / FAILED (failures=2)`。
以下2件が、Fix 1(Engine/Provider許可リスト化)導入前の古い期待値の
ままだったため失敗していた。

### 修正1: `test_unsupported_engine_returns_error_envelope`
→ `test_unknown_engine_string_is_rejected_by_pydantic_before_reaching_pipeline`
へ改名。`category == "planning_error"`という期待値を、`category ==
"request_error"`・`sub_reason == "schema_invalid"`・HTTP 422へ修正
(未知のengineはPydantic入力層で拒否され、`PromptPipeline`
(`UnsupportedEngineError`)へ到達しないため)。

### 修正2: `test_unregistered_provider_returns_provider_error`
→ `test_unknown_provider_string_is_rejected_by_pydantic_before_reaching_pipeline`
へ改名。同様に`category == "provider_error"`・`sub_reason ==
"unavailable"`という期待値を、`request_error`・`schema_invalid`・
HTTP 422へ修正。

### 強化: `test_unimplemented_provider_returns_provider_error`
既知(許可リスト内)だが未実装の`"openai"`を指定した場合の契約
(`provider_error`/`unavailable`/HTTP 503)を、`status_code`・
`sub_reason`まで明示的に検証するよう強化した(以前は`category`のみ
確認していた)。

**コード本体(schemas/ai.py・routers/ai.py・exception_handlers.py等)は
変更していない。** テストファイル(`test_http_api.py`)のテスト名・
期待値・コメントのみの修正。

---

## 7. 再実行結果(今回、事実)

```
$ cd forge && python3 -m unittest discover -s backend/tests -p "test_*.py"
Ran 265 tests in 0.028s
OK (skipped=17)

$ python3 -m unittest discover -s forge_ai/tests -p "test_*.py"
Ran 80 tests in 0.013s
OK

$ python3 -m compileall backend forge_ai
(exit code 0、エラー無し)
```

---

## 8. 禁止事項の遵守確認

| 禁止事項 | 確認結果 |
|---|---|
| Flutter/Forge Runtime/Language Schema変更 | ✅ 未変更 |
| `backend/app/ai/native/`変更 | ✅ 未変更 |
| 実LLM接続 | ✅ 無し |

---

## 9. CEO実機確認手順

```powershell
.\scripts\verify.ps1 -RunChrome
```

または個別に:
```powershell
python -m unittest discover -s backend/tests -p "test_*.py"
python -m unittest discover -s forge_ai/tests -p "test_*.py"
python -m compileall backend forge_ai
```

6章で改名・修正した2テストが、新しい期待値(422/request_error/
schema_invalid)で合格することの確認をお願いしたい。
