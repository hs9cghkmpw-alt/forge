# Local Model セットアップ / Benchmark 実行手順

FORGE-QUALITY-AI-INDEPENDENCE-003 Phase G〜I(2026-08-12)。

Forgeを「Geminiを使うアプリ」にしないための、ローカル推論の実行手順。

## この環境では実行できていない（重要）

**開発サンドボックスではLocal Modelを一度も動かせていない。**
指示書31章 最低条件E（「少なくとも1つのForge AI TaskをLocal Modelで
実際に実行し、Benchmark結果を取得する」）は**未達**である。

実測した環境条件:

| 項目 | 実測値 |
|---|---|
| `huggingface.co` | **CONNECT 403**（ネットワークポリシーによる拒否） |
| `pypi.org` | 200（到達可能） |
| Ollama | 未インストール |
| llama.cpp | 未インストール |
| GPU | 無し |
| RAM | 15 GB |
| CPU | 4 コア |
| 空きディスク | 26 GB |

pypiへは到達できるので推論ライブラリの導入自体は可能だが、
**モデル重みの取得元（HuggingFace）がネットワークポリシーで
拒否されている**ため、どのモデルも読み込めない。これは
「時間をかければ解決する」類ではなく、環境の制約である。

したがって実装したのは次までであり、実モデルに対する実行は
CEO環境で行う必要がある:

* `LocalModelProvider`（OpenAI互換HTTP、JSON抽出、再試行、エラー処理）
* `ModelGateway`（Task単位のRouting、fallback、latency計測）
* `run_benchmark()` + Impact分類データセット（16ケース）

Benchmark harness自体は**実際に走らせて確認済み**であり、
`local`が接続できない場合は`failure_rate = 1.0`として正しく記録される
（隠したり握り潰したりしない）。

## 必要なもの

以下のいずれかが満たされれば、Benchmarkを実測できる。

1. `huggingface.co` と `ollama.com` へのネットワーク許可
2. またはモデル重みが事前に配置された環境

## 手順（CEO環境）

### 1. Ollamaを入れる

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve   # 既定で 127.0.0.1:11434
```

### 2. モデルを取得する

GPU無し・RAM 15GB程度を想定した候補。**モデル名を先に決め打ちせず、
Benchmarkで比較すること**（指示書18章）。

| モデル | サイズ | 備考 |
|---|---|---|
| `qwen2.5:1.5b-instruct` | 約1.0 GB | 日本語とJSON出力が比較的安定。最初の候補 |
| `qwen2.5:3b-instruct` | 約2.0 GB | 精度優先。CPUでも動くが遅い |
| `llama3.2:1b` | 約1.3 GB | 軽量。日本語は弱め |
| `gemma2:2b` | 約1.6 GB | 比較用 |

```bash
ollama pull qwen2.5:1.5b-instruct
```

### 3. Forgeから使う

`LocalModelProvider`はOpenAI互換エンドポイントを叩くだけなので、
Ollama以外（llama.cpp の `llama-server`、LM Studio、vLLM）でも
`FORGE_LOCAL_BASE_URL` を変えれば動く。

```bash
export FORGE_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
export FORGE_LOCAL_MODEL=qwen2.5:1.5b-instruct
```

動作確認:

```bash
cd backend
python3 -c "
from app.ai.foundation.local_provider import LocalModelProvider
p = LocalModelProvider()
print(p.complete_structured('{\"impact\":\"high\"}というJSONを返して', {}))
"
```

### 4. Benchmarkを走らせる

```bash
cd backend
python3 -c "
import json
from app.ai.gateway.benchmark import run_benchmark
from app.ai.gateway.impact_benchmark import build_impact_cases
from app.ai.gateway.model_gateway import ForgeTask, ModelGateway
from app.ai.runtime.provider_router import ProviderRouter

gw = ModelGateway(ProviderRouter().resolve, default_provider='mock')
report = run_benchmark(
    gw, ForgeTask.CONVERSATION_STEP, build_impact_cases(), ['local', 'gemini'],
)
print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
"
```

`winner`が`null`なら、**どのProviderもまだこのTaskを任せられない**
という意味である（適合率90%以上かつ正答率50%以上が採用条件）。

### 5. Routingへ反映する

Benchmarkで合格したTaskだけ、`ModelGateway`のRouting表へ入れる。

```python
ModelGateway(
    ProviderRouter().resolve,
    routes={
        ForgeTask.CONVERSATION_STEP: TaskRoute(primary="local", fallback=("gemini",)),
    },
)
```

**実測前にRoutingへ入れない**（指示書20章）。現在の既定Routing表は
意図的に空であり、すべて呼び出し側指定のProviderがそのまま使われる。

## Privacy上の注意

`ModelGateway`のfallbackは、Localが失敗したときに外部API（Gemini等）へ
処理を回す。**ユーザーが「ローカルのみ」を選んでいる場合、この
fallbackは行ってはならない**（指示書21章）。現時点でLocal-only Modeは
未実装であり、Routingは開発者が明示的に設定したときだけ有効になる。
外部送信の同意管理は、Local-only Modeを実装する際に併せて必要になる。
