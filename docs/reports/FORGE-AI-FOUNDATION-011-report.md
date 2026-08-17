# FORGE-AI-FOUNDATION-011 実施報告

2026-08-14〜17 / branch `claude/forge-master-handoff-k46jns`

指示書が求めた7点＋報告17項目に答える。**§8「今回まだAPI Keyを
要求しない」を守り、実APIの新規取得は行っていない**（既存のGemini鍵での
実機確認のみ）。

---

## 0. 先に考えたこと — 4点は同じ2つの根から来ていた

指示書の「指摘をそのまま局所Patchせず、同じArchitecture上の問題から
来ていないか先に考えること」への回答。

指摘された §1〜§4 は、独立した4つのバグではなく **2つの根**を持つ。

### 根A — 同一性(Identity)が足りていない

| 指摘 | 何の同一性が欠けていたか |
|---|---|
| §1 汎用`cloud`1枠 | **Providerの同一性**。昨日のGroqと今日のCerebrasが同じ統計へ混ざる |
| §3 `ranking_for()` | **比較条件の同一性**。違う入力で測った数字を並べていた |

### 根B — 文脈(Context)が下位へ伝播していない

| 指摘 | 何が伝わっていなかったか |
|---|---|
| §2 Structured Output | **失敗が誰のせいか**が上位へ伝わらない(400が全部「Forgeの誤り」に潰れた) |
| §4 Latency Budget | **Taskの予算**が実行へ伝わらない(45秒と宣言して120秒待つ) |

この2つを軸に直したので、以下の修正は互いに独立したPatchではない。

---

## 1. §1 — Multi-Provider Identity

**Protocolの共通化とIdentityの共通化を分けた。**

* `provider_id` が唯一の識別键(Quota / Circuit Breaker / Benchmark /
  Experience / Provenance のすべて)
* `Protocol.OPENAI_COMPATIBLE` は**通信の形**でしかなく、Identityでは
  ない
* HTTP通信実装は**1つのまま**。Provider追加は
  `ProviderDefinition` の宣言1件＋環境変数3つで済み、**コードのコピーは
  発生しない**

```python
_PROTOCOL_FACTORIES = {
    ProviderProtocol.OPENAI_COMPATIBLE: OpenAICompatibleCloudProvider,
}
```

Groq / Cerebras / OpenRouter / Together / DeepInfra を**宣言だけ**追加
した(鍵が無いのでAuto Discoveryが候補から外す)。

**最小の回帰**: 010の`cloud`という名前は削除した。中身が入れ替わりうる
名前は、統計を混ぜる。

回帰テスト `test_multi_provider_identity.py`(17件)。

---

## 2. §2 — Structured Output の実バグ

**Forge自身のschema誤りと、Providerの対応範囲の限界を分けた。**

```
INVALID_REQUEST          Forge側の誤り。相手を変えても直らない → 巡回を止める
UNSUPPORTED_OUTPUT_MODE  相手の対応範囲の問題      → 巡回を止めてはならない
```

011以前は両方がHTTP 400として`INVALID_REQUEST`へ潰れており、
`json_schema`を知らないProviderが1つあるだけで**全Routingが停止**しえた。

modeの梯子を作り、**安全なdowngradeを1回だけ**許す:

```
STRICT_JSON_SCHEMA → JSON_SCHEMA → JSON_OBJECT → PROMPT_JSON → UNSUPPORTED
```

`FourHundredReading` が400の読み方を3つに分ける:

* `MODE_UNSUPPORTED` — 1段だけ緩めて再試行
* `FORGE_REQUEST_INVALID` — 緩めない。巡回も止める
* `AMBIGUOUS` — 緩めないが、他Providerは試す

**宣言は仮説として扱う**(§46)。実際に400が返れば、その事実の方を採る
(`StructuredOutputCapabilityStore`)。

回帰テスト `test_structured_output_modes.py`(16件)。指示書が名指しした
4つの回帰すべてを含む。

---

## 3. §3 — Benchmark Integrity

### 3-1. dataset_idの一致を検証していなかった

`dataset_fingerprint()`(順序非依存のSHA256、16文字)を導入し、
比較键を `(dataset_id, dataset_hash)` にした。**同じ名前でも中身が違えば
別物**として扱う。名前だけ揃えて中身が違うDatasetは、最も気付きにくい形で
比較を壊す。

### 3-2. `schema_valid_rate` を足切りにするか

**足切りにした。** CEOの例で考え直した結果である。

```
A: accuracy 0.95 / schema_valid 0.40
B: accuracy 0.90 / schema_valid 1.00
```

Aは10回に6回**構造化出力が壊れる**。壊れた応答はForgeでは
`STRUCTURED_OUTPUT_FAILURE`になり、accuracy以前に**使えない**。
accuracyは「答えられたとき」の質であって、「答えられるか」ではない。

**私は以前これと逆のことをコメントに書いていたので、コードの中で明示的に
撤回した。**

### 3-3. Verification区分

```
REAL / DOUBLE / FIXTURE / UNVERIFIED(既定)
```

**REALだけがRoutingを動かせる。** Test Doubleで測った数字は構造的に
弾かれる。

回帰テスト `test_benchmark_evidence.py`(26件)。

---

## 4. §4 — Latency Budget を Hard Budget にする

指示書の例そのものを実装した。

> budget 45秒 / Provider A が30秒で失敗 → Provider B へ使えるのは
> 残り約15秒であり、新たに60秒待ってはいけない

`SupportsDeadline` を**任意のCapability**として導入した
(`LLMAdapter`の契約は変えない——全実装とTest Doubleが同時に壊れる)。

```python
remaining_ms = profile.latency_budget_ms - elapsed_ms
if remaining_ms <= _MIN_USEFUL_ATTEMPT_MS:
    break                      # 始めても意味が無い
attempt, result = self._try_one(..., remaining_ms=remaining_ms)
```

deadlineを受け取れないAdapterは、Registryの`nominal_timeout_seconds`と
比べ、**入りきらないと分かっている試行は始めない**。ただし宣言が無い
Adapter(テストのFake等)は**通す**——判断の根拠が無いのに除外すると、
実際には即答するものまで締め出す。

`copy.copy`で複製するので、共有インスタンスは書き換えない。

回帰テスト `test_latency_budget.py`(13件)。

---

## 5. §5 — Local AI Learning Signal

**明示的なACCEPTと「ただ訂正されなかった」を分けた。**

```
ACCEPTED   利用者が明示的に「それでいい」と言った  ← 唯一の強い正例
CORRECTED  次のターンで訂正された                  ← 強い負例
ABANDONED  会話がそこで終わった                    ← 弱い負例
UNKNOWN    既定値。訂正されなかっただけ            ← 教師信号にしない
```

**Forgeは既にACCEPTEDを持っていた**(`HypothesisState.ACCEPTED`)。
記録側で捨てていた、というのが010の実態である。

> **R0(2026-08-17)で本番から実際に書かれるようになった。**
> 011の時点では型として分けただけで、本番から`ACCEPTED`が書かれる経路は
> 無かった。`docs/reports/FORGE-ROADMAP-R0-report.md` 参照。

---

## 6. §6 — Documentationの矛盾

2件とも直した。

1. `transform.aggregate = 動作 / Compiler未接続` と
   「4つがいずれも未実装」が矛盾していた → STATUS.mdを実態へ合わせた
2. Gemini-429の記述が Router Architecture と食い違っていた → 書き直した

---

## 7. §7 — CI

**実装した。** `.github/workflows/ci.yml`、初回実行で3ジョブとも green。

```
backend + forge_ai (Python 3.11)   success
backend + forge_ai (Python 3.12)   success
frontend (Flutter analyze + test)  success
```

**実APIは呼ばない**(`FORGE_LIVE_TEST`未設定 → Live TestはSKIP、
CIにAPIキーを置かない)。設計提案に留めず実装したのは、主要修正が
先に片付いたためである。

---

## 8. §8 — API Keyを要求しないこと

**守った。** 新しい鍵は1つも取得していない。

Groq / Cerebras / OpenRouter / Together / DeepInfra は**宣言のみ**で、
鍵が無いのでAuto Discoveryが候補から外す。実機確認は既存のGemini鍵の
範囲で行った。

### ただし、実APIが必要な段階に入った(2026-08-17判明)

R0.1の検証中に、429の本文から実測した:

```
"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
"quotaValue": 20
```

**Gemini無料枠は1日20回/Model。** Model 3つで60回/日が上限であり、
1日20アプリ程度で止まる。枠は鍵ごとに独立しているため、**Providerを
増やす以外に方法が無い**(TD66)。

Adapterは実装済みなので**コード変更は不要**。環境変数3つで載る。

```
FORGE_GROQ_API_KEY / FORGE_GROQ_BASE_URL / FORGE_GROQ_MODEL
```

推奨順: Groq → Cerebras → OpenRouter(いずれもOpenAI互換・無料枠あり)。

---

## 9. 検証区分(§39)

| 区分 | 内容 |
|---|---|
| **実測(REAL)** | 実Geminiでの`/converse`・`/generate`往復。Model別の200/503分布。429本文の`quotaValue`。CIの3ジョブ |
| **Test Double** | Provider fallback・Circuit Breaker・mode downgrade・Hard Budget。**Benchmarkには入らない**(`Verification.DOUBLE`) |
| **未検証** | Groq等の実APIでの動作。宣言のみで一度も呼んでいない |

**429は意図的に出していない**(§38)。上に載せた429は、R0.1の検証で
自然に到達したものである(枠を消費する目的の呼び出しはしていない)。

---

## 10. テスト

```
backend/tests   1079 passed / 16 skipped(うち3件はLive API Test、既定SKIP)
forge_ai/tests   521 passed
frontend          476 passed / flutter analyze 0件
CI               3ジョブとも green
```

011で追加したファイル:

| ファイル | 件数 |
|---|---|
| `test_multi_provider_identity.py` | 17 |
| `test_structured_output_modes.py` | 16 |
| `test_latency_budget.py` | 13 |
| `test_benchmark_evidence.py` | 26 |

すべて「配線・ガードを外すと落ちる」ことを実際に確認済み。

---

## 11. できていないこと(正直な申告)

1. **実APIでの多Provider検証** — Groq等は宣言のみ。鍵が無い
2. **Local AIの実モデル実行** — 0回(環境制約 TD51)
3. **Benchmarkの実測データ** — 配線は済んでいるが REAL の記録が無いので
   宣言順で動く
4. **`ABANDONED`が書かれない** — 会話の放棄を検出していない
5. **Experienceの永続化** — プロセス内メモリのみ(TD41)

---

## 12. 関連文書

* `docs/PRODUCT-DIRECTION.md` — 上位方針(変更不可)
* `docs/ROADMAP-TO-TARGET.md` — 完成図までの段取り(閉ループ版)
* `docs/reports/FORGE-AI-FOUNDATION-010-report.md` — 前段
* `docs/reports/FORGE-ROADMAP-R0-report.md` — R0 / R0.1
* `TECH_DEBT.md` TD64 / TD65 / TD66
