# FORGE-AI-FOUNDATION-010 実施報告

2026-08-14 / branch `claude/forge-master-handoff-k46jns`

---

## 0. 一番大事なこと

**Phase Bの監査で、実バグを1件見つけて直した。**

`FORGE_DEFAULT_PROVIDER=mock`（＝運用者が「Mockを使え」と明示した状態）で
`/converse` を呼ぶと:

* HTTPレスポンス: `provider: "mock"`, `simulated: true`
* 実際の動作: **利用者の入力を本物のGeminiへ送信していた**

Router内部の状態（`gemini available successes=1`）で裏を取った。表示の
誤りではなく、**情報が外へ出る側の誤り**である。

原因は2つ、どちらも「Providerの決定が1箇所に無い」に帰着する:

1. `default_catalog()` が固定リストで、`FORGE_DEFAULT_PROVIDER` を読んでいなかった
2. レスポンスの `provider` / `simulated` が「選ばれる**はず**だった名前」から
   作られており、実際に応答したProviderと無関係だった

「Silent Mock fallback禁止」（004 §9）の裏返しで、**Silent Cloud送信**の方が
害が大きい。両方直した上で、実機で再現・修正確認済み。

---

## 1. 配線漏れの3例目

ご指摘の「基盤はあるのに製品では使っていない」問題が、**もう1件見つかった**。

Router経由になっていたのは `/converse` の会話ステップだけで、以下は
`ProviderRouter.resolve()` を直接呼んでいた:

| 経路 | 状態（監査時） |
|---|---|
| `/converse` 会話ステップ | Router経由 ✅ |
| `/converse` BUILD（Cognitive Pipeline） | **迂回** |
| `/generate` | **迂回** |
| `/generate/confirm` | **迂回** |
| `/update` | **迂回** |
| `/converse` UPDATE | Router経由だがTaskが誤り |
| `ModelGateway` | **本番から一度も呼ばれない死んだ層**（TD59） |

これで3回目なので、**テストの作り方を変えた**。

### §10 Anti-Bypass Regression

> 「AIRouterを呼べる」だけでは不十分。「AIRouterを通らずAIを呼べない」ことを
> Regression化してください。

「Routerを呼んでいるか」をassertするだけでは足りない——**Routerも呼び、かつ
別経路でも呼んでいる**という状態を見逃すからである。塞ぐべきは
「Routerを通らない経路が存在しないこと」の方である。

実装: `ProviderRouter.resolve()`（Provider名→Adapterの唯一の解決口）を
**爆発するように差し替える**。Router経由の呼び出しは注入したRouter自身の
resolveを使うので影響を受けない。迂回があればその瞬間に落ちる。

**この回帰テスト自体が置物でないことも確認した**: `prompt_pipeline.py` へ
迂回を再導入すると4件落ち、戻すと通る。

副産物として、自分の書いたコードが1度誤検知した。名前の存在確認に
`resolve()`（Adapterを取り出すAPI）を使っていたためで、`is_registered()` を
分けた。**確認しただけ**と**Routerを迂回してAIを呼んだ**がコード上
区別できない状態だった、ということである。

---

## 2. 各Phaseの結果

| Phase | 内容 | 状態 |
|---|---|---|
| A | Conversation Foundation 確認 | 完了（007で実装済みを再確認） |
| B | AIRouter 完全配線 + 迂回の回帰化 | **完了**（実バグ1件修正） |
| C | Provider Registry | 完了 |
| D | Secret / API Key 境界 | 完了 |
| E | 汎用OpenAI互換Adapter | 完了 |
| F | Provider Auto Discovery | 完了 |
| G | 失敗分類の順序 | 完了 |
| H | 2つ目のCloud Provider | **実装完了・実APIでは未検証**（TD62） |
| I | Live API Test | **完了・実行して確認済み（実Gemini）** |
| J | Task Benchmark 基盤 | 配線完了・**データ待ち**（TD63） |
| K | Local AI 学習基盤 | **境界のみ**（収集も学習も未実施、TD64） |

### Phase C/D — Registryと秘密の境界

Providerの知識が3箇所に散っていた（`ProviderRouter._providers` /
`ai_router._KNOWN_MODELS` / `default_catalog()`）。1つ足すには3箇所を
揃える必要があり、揃え忘れてもテストは通る——TD37と同じ形である。
`provider_registry.py` を唯一の宣言とし、他はそこから導出する。

**「宣言されている」と「動く」を分けた**のが要点。`openai`/`claude` は
鍵の変数名を宣言しているが実装はスタブなので、鍵を設定しても候補に
ならない。必ず失敗する相手に試行予算を渡さない。

秘密については、`.gitignore` が `.env` と `backend/.env` の**完全一致2件**
しか見ておらず、`.env.local` や `backend/.env.production` が素通りして
いた。除外を既定にし、`.env.example` だけを明示的に戻す形へ変更。
Registryが持つのは環境変数の**名前**だけで、`is_configured` は真偽値しか
返さない（長さも先頭数文字も返さない——診断には便利だが、ログへ断片が
流れ出す経路を作ることになる）。

### Phase G — 失敗分類は弱い証拠を最後に使う

従来は例外メッセージの文字列マッチしか無く、実APIの文言が想定と違えば
`UNKNOWN` へ落ちていた。Adapterは HTTP応答を直接見られるので、
**強い証拠から順に**使う:

1. 構造化エラー（`{"error": {"type": "insufficient_quota"}}`）
2. HTTPステータス（401/403/404/429/5xx）
3. ヘッダ（`Retry-After`、`x-ratelimit-*`）— **いつ復帰するか**はここにしか無い
4. 本文テキスト（枠切れは429以外でも来る）
5. 文字列マッチ — **最後**

逆順だと「429という明確な事実があるのに、文言に rate limit が無いから
UNKNOWN」が起きる。また 429 + `insufficient_quota` は**枠切れ**であって
流量制限ではない（復帰条件が違うので、取り違えると戻らないProviderを
叩き続けるか、戻るProviderを長く捨てる）。

### Phase J — 測っていないものでRoutingを決めない

`task_accuracy = 0.85` という数字は、それ単体では意味が無い。いつ・何を・
何件・**どうやって**測ったかが要る。最後が決定的で、Test Doubleは
「常に正解するAdapter」をいくらでも作れるので、その数字がRoutingへ
流れ込むと**測っていないもので本番の経路が決まる**。

`Verification`（REAL / DOUBLE / FIXTURE / UNVERIFIED、既定はUNVERIFIED）が
関門である。順位が返るのは REAL・16件以上・30日以内が2 Provider以上
揃ったときだけ。

**`AIRouter._order()` へ配線済みである。** 今効かないのは
**コードが無いからではなくデータが無いから**であり、実測を入れれば
自動的に効き始める。テストで両方向を固定した（データを入れれば実際に
順序が変わる / Doubleでは変わらない）。

### Phase K — 学習の境界を先に置く

学習用データの収集は**後から安全にはできない**。とりあえず保存してから
選ぶ、では、その時点で既に利用者の入力が保存済みである。

`ExperienceRecord` には発話・生成物・応答本文を入れられるフィールドが
**そもそも無い**。「気を付ける」運用はいずれ破られるので型で塞いだ。
訂正は**有無**だけを持ち、内容（＝利用者の発話）は持たない。

Shadow Modeは設計のみ（有効化と割合の両方を明示しないと動かない）。
`TrainingProvenance` の既定は `UNKNOWN` で、記録漏れが「公開データのみで
学習済み」という主張へ化けないようにしてある。既知Modelは全て `UNKNOWN`
である（Provider公称は検証ではない）。

---

## 3. 検証区分（§39）

| 区分 | 対象 | 内容 |
|---|---|---|
| **REAL** | Gemini | `/converse` 実呼び出し（バグ再現1回・修正確認1回）、Live API Test 2回 |
| **DOUBLE** | Router契約 / OpenAI互換Adapter / 失敗分類 / Benchmark / 学習境界 | 実HTTPなし。Test Double |
| **DOUBLE** | Multi-Cloud fallback | A→B の切替が成立することのみ。**複数Cloudの実地確認ではない** |
| **UNVERIFIED** | `cloud` 枠、`local` 実モデル | Adapterはあるが実APIで一度も動かしていない |

**実APIで動作を確認できているのはGeminiだけである。** したがって
「Multi-Cloud Routingが動く」とは書いていない（§62）。

**実API消費量（§38）**: 本作業全体でGemini呼び出し **合計4回**。
429を出すための枠消費は**行っていない**——Rate Limitや枠切れの挙動は
Test Doubleで検査している。

---

## 4. テスト

| 対象 | 件数 | 状態 |
|---|---|---|
| `backend/tests` | **989** | 全green（skip 16。うち3件はLive API Test、既定SKIP） |
| `forge_ai/tests` | 521 | 全green |
| `ruff check app` | 5件 | いずれも `app/main.py` の意図的な E402 のみ |

新規テストファイル:

* `test_router_anti_bypass.py`（7）— 迂回の不在を固定
* `test_provider_registry.py`（17）— 宣言⇄実装の双方向一致、秘密の非混入
* `test_openai_compatible.py`（33）— Adapter契約、証拠順の分類
* `test_benchmark_evidence.py`（17）— Doubleの数字がRoutingへ流れないこと
* `test_learning_foundation.py`（18）— 利用者入力が記録へ入りえないこと
* `test_live_api.py`（3）— 実API。既定SKIP

**ガード自体の検証も行った**（テストが置物でないことの確認）:

* 迂回を再導入 → anti-bypass 4件失敗、戻すと通る
* 鍵形式の文字列をソースへ仕込む → 秘密検査が失敗、戻すと通る

---

## 5. §71 — 取得をおすすめする無料Cloud API（上位3件）

**先に申告**: この開発環境は各Providerの公式ドキュメントへのアクセスが
proxyで禁止されている（`console.groq.com` / `openrouter.ai` /
`docs.cerebras.ai` いずれもegress拒否）。以下は**Web検索の二次情報**で
あり、**公式ドキュメントで検証していない**。数値は変わりうるので、
取得時に公式ページでご確認ください。

この制約があるため、Forge側には特定Providerのエンドポイントを
**書き込んでいない**。環境変数3つ（`FORGE_CLOUD_BASE_URL` /
`FORGE_CLOUD_API_KEY` / `FORGE_CLOUD_MODEL`）を設定すれば、
**コード変更なしで**Routingへ載る形にしてある。

### 1位: Groq — 最優先で取得する価値がある

* OpenAI互換（`/v1/chat/completions`）なので、Forgeは**設定するだけ**で使える
* 無料枠・クレジットカード不要
* 二次情報では 30 req/分・14,400 req/日程度
* 速度が非常に速い（専用ハードウェア）ので、会話の待ち時間が縮む

**Forgeにとっての意味**: Geminiの枠が切れたときの受け皿として、
最も導入コストが低い。

**注意点として重要**: 複数のAPI Keyを作っても**組織単位で制限がかかる**と
報告されている。これはご指示の§23「API Key複数化による制限回避は禁止」と
一致しており、Forgeもその方針で実装している。

### 2位: Cerebras — 日次のトークン量が大きい

* OpenAI互換、クレジットカード不要
* 二次情報では 1日100万トークン程度
* ただし**無料枠はコンテキスト長が短い**（8K程度）との報告がある

**Forgeにとっての意味**: Forgeは会話履歴と既存Forge Documentを送るため、
UPDATE経路では8Kが窮屈になる可能性がある。**会話ステップ用**としては
十分だが、生成本体には向かないかもしれない——これはTask別Routingが
効く場面である（Taskごとに別Providerを選べる形にしてある）。

### 3位: OpenRouter — 1つの鍵で多数のモデルへ届く

* OpenAI互換、無料枠のあるモデルが複数
* 1つの鍵で複数Providerのモデルを試せる

**Forgeにとっての意味**: どのモデルがForgeのTaskに向くかを
**Benchmarkで比べる**ための入口として便利である（Phase Jの基盤は
まさにこれを受ける形になっている）。ただし本番の主経路としては、
中間層が1つ増える分だけ障害点も増える。

### 取得順のおすすめ

1. **Groq を1つ取る** → `FORGE_CLOUD_*` に設定 → `FORGE_LIVE_TEST=1` で
   `tests/test_live_api.py` を実行。これでTD62が解消し、
   **初めて「Multi-Cloud Routingを実機確認した」と書ける**
2. その状態で Benchmark を走らせると、Gemini と Groq の2 Providerが
   揃うのでTD63（品質Routingのデータ待ち）も解消する

Sources:
- [Groq API Free Tier Limits in 2026](https://www.grizzlypeaksoftware.com/articles/p/groq-api-free-tier-limits-in-2026-what-you-actually-get-uwysd6mb)
- [Groq Free Tier Limits 2026: 30 RPM, 6K TPM, 14.4K Req/Day](https://tokenmix.ai/blog/groq-free-tier-limits-2026)
- [Free Cerebras API Key: Base URL, Rate Limits & 8 Models](https://freellm.net/providers/cerebras)
- [Free LLM API Tiers in 2026: Groq, Cerebras, Mistral & More](https://ianlpaterson.com/blog/free-llm-api-2026/)
- [Free LLM API in 2026: 13 Options Ranked and Compared](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/)

---

## 6. できていないこと（正直な申告）

| 項目 | 状態 | 記録 |
|---|---|---|
| 2つ目のCloudの実API検証 | Adapterのみ。鍵もドキュメントも無い | TD62 |
| Benchmarkによる品質Routing | 配線済み・実測データ0件 | TD63 |
| Local AI 学習 | 境界のみ。収集も学習も未実施 | TD64 |
| Local実モデル実行 | 環境制約（huggingface.co拒否・GPU無し） | TD51 |
| Privacy Policy | 未完成。内容によるsensitivity判定なし | TD60 |
| Provider状態の共有 | プロセス内メモリのみ | TD41 / TD61 |

`ModelGateway` は削除したのでTD59は完全に解消した。

---

## 7. 変更したファイル（主要）

**新規**

* `app/ai/gateway/provider_registry.py` — Providerの唯一の宣言
* `app/ai/gateway/tasks.py` — `ForgeTask`（`model_gateway.py` から分離）
* `app/ai/gateway/benchmark_evidence.py` — 測定条件つきのBenchmark記録
* `app/ai/gateway/learning_foundation.py` — 学習の境界
* `app/ai/foundation/openai_compatible.py` — 汎用Adapter + 失敗の正規化
* `app/ai/foundation/cloud_provider.py` — 2つ目のCloud枠

**削除**

* `app/ai/gateway/model_gateway.py` — `AIRouter` と重複、本番未使用

**主な変更**

* `app/ai/gateway/ai_router.py` — Catalog環境依存化、実使用Provider記録、品質順の配線
* `app/routers/ai.py` — `/update` をRouter経由へ、報告するProvider名を実行後の事実へ
* `app/ai/runtime/prompt_pipeline.py` — Cognitive PipelineをRouter経由へ
* `app/ai/foundation/local_provider.py` — 汎用Adapterの上へ載せ替え
* `backend/.env.example` — 値を書かず、変数名と効果だけを記載
* `.gitignore` — `.env*` を除外の既定に
