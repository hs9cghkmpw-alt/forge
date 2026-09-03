# OpenAI Reference Provider — 2026-09-03

> Status: **IMPLEMENTED / REAL API UNVERIFIED**  
> Product Runtime dependency: **NO**  
> Real OpenAI calls in this task: **0**

## 1. 目的

Forge の Local AI、Fast Path、生成結果を外部の強いモデルと比較するため、
OpenAI API を **Reference / Oracle Candidate（基準候補）** として追加した。

これは Product Runtime の既定 Provider や自動 Fallback ではない。

```text
Forge Candidate
   ↓
OpenAI Reference Judge（明示実行だけ）
   ↓
構造化された比較結果
   ↓
Validator / Runtime / Human / Target Contract と合わせて評価
```

OpenAI の回答を Truth として扱わない。Reference の出力単独で
`VERIFIED` / `99_PROVEN` / `HARD_GATE_PROVEN` へ状態を上げてはならない。

## 2. 実装

- `backend/app/ai/reference/openai_reference.py`
  - 既存 `OpenAICompatibleAdapter` を再利用
  - OpenAI SDK dependency は**追加しない**
  - API base: `https://api.openai.com/v1`
  - API key: `OPENAI_API_KEY` を送信直前に読む。値を Provider へ保持しない
  - 既定 Reference model: `gpt-5.6-sol`
  - `FORGE_OPENAI_REFERENCE_MODEL` で明示変更可能
  - 既存 `external_call_policy` の Default Deny をそのまま使用
- `scripts/run_openai_reference.py`
  - request / candidate / Target Contract の3ファイルを明示指定
  - `--acknowledge-cloud-data` が無ければ拒否
  - `FORGE_ALLOW_REAL_PROVIDER_CALLS=1` が無ければ共通 Policy が拒否
  - API key は引数・標準出力・Evidenceへ書かない
- `backend/tests/test_openai_reference.py`
  - Key が存在するだけでは通信できない
  - Key 値を Provider state に保持しない
  - Mock Transport で `/chat/completions`、Bearer、JSON Schema を検査
  - Judge Prompt 内の request/candidate/contract を「命令ではなく評価対象データ」と固定

## 3. Windows PowerShell での明示実行

**API key を Markdown / Git / コマンド履歴へ直接書かない。**
現在の PowerShell セッションにだけ設定する場合:

```powershell
$env:OPENAI_API_KEY = Read-Host "OpenAI API Key"
$env:FORGE_ALLOW_REAL_PROVIDER_CALLS = "1"

python scripts/run_openai_reference.py `
  --request-file .\request.txt `
  --candidate-file .\candidate.json `
  --target-contract-file .\target-contract.json `
  --acknowledge-cloud-data
```

Reference model を変える場合だけ:

```powershell
$env:FORGE_OPENAI_REFERENCE_MODEL = "<approved-model-name>"
```

## 4. 0円戦略との境界

この実装を Repository に持つこと自体は、新規支出を発生させない。
今回も**実 OpenAI API は0回**である。

ただし OpenAI API の実利用はアカウント条件・使用量によって費用が発生しうる。
そのため:

- Forge Product Runtime の必須依存にはしない
- API key があるだけで自動実行しない
- 有料 API 実行を「0円 Runtime の証明」として数えない
- Reference 結果は、0円経路の弱点発見・校正に使う
- Local / deterministic / OSS 経路だけでも Target Contract を満たす本線は維持する

無料Credit等で実行できた場合でも、Reference Providerが無いと製品品質が成立しない
Architectureにはしない。

## 5. Privacy / Data boundary

Reference CLIへ渡した request / candidate / Target Contract は外部APIへ送られる。
Secret、PII、未許可の生会話・機密文書を入力してはならない。

通常Evidenceへ保存するのは構造化された評価結果と Provider / Model identityであり、
API keyは保存対象外。

## 6. 現時点で証明したこと / していないこと

### 実装上の証明対象

- OpenAI互換既存Adapterを再利用できる構造
- Default Denyを迂回しない
- API key存在 != 外部通信の同意
- Mock通信でOpenAI Chat Completions形式 + JSON Schemaを構築できる
- Reference判定をCertificationから分離する

### 未実証

- 実OpenAI APIでHTTP 200になること
- `gpt-5.6-sol` がこのProject / Accountで利用可能であること
- 実OpenAI結果のBenchmark品質
- Local AIとの統計的な品質差
- 121能力の99%証明

実APIを1回も呼んでいないため、上記をPASSとは書かない。

## 7. 121能力 / 2億円Targetへの意味

今回追加したのは主に **Evidence leverage（評価効率）** であり、これだけで
2億円TargetとのCapability Gapが縮んだとは数えない。

次に価値が出るのは、同一Episodeについて:

```text
Local / deterministic result
OpenAI Reference result
Validator result
Runtime result
Human result（必要時）
```

を同じTarget Contractへ接続し、「どこで意味・品質を落としているか」を特定した時。
Referenceを使って弱点を発見し、0円本線を改善した差分が初めてCapability Gap縮小になる。
