# FORGE-QUOTA-AWARE-AI-ROUTER-ARCH-REVIEW

FORGE-QUOTA-AWARE-AI-ROUTER-008 §50 への回答。2026-08-13。
現物のコードを監査した上での批判的レビュー。

---

## 0. 結論を先に

1. **現行`ModelGateway`は本番コードから一度も呼ばれていない。**
   `_DEFAULT_ROUTES`も空である。Quota対応を足す前に、まずこれが
   実際に経路上に立っていないという事実から始める必要がある。
2. Quotaの**正確な残量取得は前提にできない**。Providerごとに単位も
   粒度も異なり、返さないものもある。「不明」を「無制限」と扱わない
   設計が要る(§9)。
3. **エラーを1種類として扱っている**のが現行の最大の欠陥。
   400(不正リクエスト)で全Providerを巡回するのは無駄であり、
   Quota消費でもある。
4. MVPは**API Key不要で完全にテストできる**。Provider健康状態・
   Circuit Breaker・Fallbackは決定的なTest Doubleで証明できる(§39)。
5. **Mockは本番Routingの候補にしない**(§22)。明示的に要求された
   ときだけ使える「テストモード」として扱う。

---

## 1. 現行Model Gateway(現物)

`backend/app/ai/gateway/model_gateway.py`(221行)。

```python
def generate(self, task, prompt, response_schema, *, provider=None):
    route = self.route_for(task, requested=provider)
    for name in (route.primary, *route.fallback):
        try:
            return self._resolve(name).complete_structured(prompt, response_schema)
        except Exception:          # ← すべて同じ「失敗」
            continue
    raise ModelGatewayError(...)
```

良い点:

* Provider実装を一切importしない(抽象の境界は正しい)
* Task概念(`ForgeTask`)が既にある
* 試行履歴(`ProviderAttempt`)を返す

---

## 2. 現行Provider実装

* `ProviderRouter` — 名前 → `LLMAdapter`の解決。8名前を登録。
* `GeminiProvider` — 実装済み。`RuntimeError`を投げる(429含む)。
* `LocalModelProvider` — OpenAI互換。`LocalModelError`。
* `MockLLMAdapter` — 決定的。**`ProviderRouter`の既定候補**。
* その他5つ — `NotImplementedError`のスタブ。

---

## 3. 問題(重大な順)

### 3.1 Gatewayが経路上に無い(最重大)

```
$ grep -rn "ModelGateway" app/ | grep -v app/ai/gateway/
→ コメント2件のみ。**呼び出しゼロ**
```

`/converse`も`/generate`も`ProviderRouter().resolve(name)`で
Providerを直接取っている。したがって現状、

* Task別Routingは**1度も起きていない**
* fallbackは**1度も起きていない**
* `ForgeTask`は**分類として存在するだけ**

007 §10でご指摘いただいた「`classify_correction`がテストからしか
呼ばれていない」と**同じ形の問題**である。基盤を作って配線を忘れると、
テストは通るのに製品は何も変わらない。

**したがって本Phaseの最優先は、Quotaの精緻化ではなく「Routerを
実際に経路へ立てること」である。**

### 3.2 エラーが1種類

`except Exception`。結果として:

* 400(schema不正)でも全Providerを試す → Quotaを無駄に消費し、
  しかも**どのProviderでも同じ失敗をする**(§19、§11)
* 401(認証)でも毎回試す → 設定ミスが検出されない
* 429(Quota)と500(一時障害)が区別できない → 復帰戦略が立たない

### 3.3 Provider状態が無い

枯れたProviderへ毎回投げる。Circuit Breakerが無い(§8)。

### 3.4 Latency予算が無い

`(primary, *fallback)`を順に試すだけ。各60秒なら最悪4分待たせる(§28)。

### 3.5 Mockが本番候補

`default_provider="mock"`。全Cloud失敗 → Mock → **偽のTool**という
経路が構造上ありうる(§22で明確に禁止)。

### 3.6 Structured Output要件が表現できない

Taskが厳密なschemaを要求しても、対応しないModelを除外できない(§17)。

---

## 4. Quota取得可能性(§47-1〜6への回答)

**正確なリアルタイム残量は、一般には取得できない。** 理由:

| 問題 | 実態 |
|---|---|
| 単位の違い | RPM / TPM / RPD / 同時実行数が混在。1つの数値に潰せない |
| 粒度の違い | Model単位・Project単位・Account単位が混在 |
| 返さないProvider | ヘッダを返さない、あるいは一部しか返さない |
| Reset時刻不明 | `retry-after`が無い場合、いつ復帰するか分からない |
| 共有Quota | 複数プロセス・複数ユーザーで同じQuotaを消費する |

したがってQuotaは**3状態**で持つ(§9):

```
EXACT      Providerが明示した残量(ヘッダ等)
ESTIMATED  Forge側の使用履歴からの推定
UNKNOWN    不明 ← **「無制限」とは絶対に扱わない**
```

`UNKNOWN`の扱いが設計の要点である。**楽観にも悲観にも倒さない**:
候補からは外さないが、`EXACT`で余裕があるProviderより優先はしない。

---

## 5. 採用するRouter Architecture

```
Conversation / Pipeline
        │  (Providerを知らない。Taskだけを知る)
        ▼
   TaskRequirements        strict schema? / sensitivity / latency budget
        ▼
     AIRouter
        ├ 候補列挙        Task適性・structured output対応で絞る
        ├ 除外            OPEN(Circuit Breaker)/ QUOTA_EXHAUSTED / mock
        ├ 並べ替え        quality → quota余裕 → latency
        ├ 実行            1つずつ(§29: 並列hedgingはMVPで採用しない)
        ├ 失敗分類        ErrorKind へ正規化
        └ 記録            health / quota / latency を更新
        ▼
   RoutedResult
```

**Conversation Engineは1行も変えない。** 既に抽象`AIProvider`を
受け取る設計なので、Routerが「Taskに束ねたAdapter」を渡せば足りる。
Provider固有ロジックがConversation層へ入らない(§46)。

---

## 6. Error Model(§19)

```
AUTH                   設定ミス。**そのProviderは以後除外**。他へfallback可
QUOTA_EXHAUSTED        枠切れ。reset時刻まで除外。他へfallback可
RATE_LIMITED           一時的。cooldown後に再開。他へfallback可
TIMEOUT                他へfallback可
NETWORK                他へfallback可
MODEL_UNAVAILABLE      そのModelのみ除外。同Providerの他Modelは可
PROVIDER_SERVER_ERROR  5xx。Circuit Breakerの対象
INVALID_REQUEST        **fallbackしない**。他Providerでも同じ結果
STRUCTURED_OUTPUT_FAILURE  同Providerで1回だけ再試行。だめなら他へ
LOCAL_RESOURCE_ERROR   Local固有(RAM不足・モデル未取得)
UNKNOWN                安全側=fallback可、ただしretry予算を消費
```

**`INVALID_REQUEST`でfallbackしないのが重要**である。Forge側の
プロンプト/schemaの誤りをProvider巡回で隠すと、原因が永久に分からず、
Quotaだけが減る。

分類は**例外型と文字列の両方**から行う。既存Providerは
`RuntimeError("429 ...")`のような形で投げており、型だけでは足りない
——これは既存実装に合わせるための現実的な妥協であり、Provider側を
先に作り直すより安全である。

---

## 7. Provider / Model の分離(§11)

Provider健全性とModel可用性は別物である(Provider正常・特定Model廃止)。
ただし**MVPでは1 Provider = 1 Modelとして扱う**。理由: 現行の
`LLMAdapter`はModel選択のinterfaceを持たず、二階層を今入れると
「使われない抽象」がもう1つ増える(§3.1の再来)。

`ModelDescriptor`(id / provider / structured_output対応 / context長 /
task別品質)は**型として用意し、Registryは最小**にする。実際の品質は
Benchmarkで埋める(§13)——Provider公称値を固定値として書き込まない(§12)。

---

## 8. Health / Circuit Breaker(§7・§8)

```
AVAILABLE ──連続失敗 N回──▶ OPEN ──cooldown経過──▶ HALF_OPEN
    ▲                                                  │
    └──────────── 成功 ────────────────────────────────┘
                       │ 失敗
                       ▼
                     OPEN(cooldownを延ばす)
```

`QUOTA_EXHAUSTED`は失敗回数と**別に**扱う。枠切れは故障ではないので、
Circuit Breakerではなく`reset_at`までの除外で表す。

Health Checkのために生成Requestを投げない(§30)。状態は**実際の
利用結果からのみ**更新する。

---

## 9. Local戦略(§5・§43)

Localは「予備」ではなく、**Quotaを消費しない第一候補**である。
ただし「LocalはQuota無料だから常にLocal」とはしない——品質が
足りなければProduct Qualityを壊す(§21)。

判定は**Benchmark閾値**で行う(§13)。Benchmarkが無いTaskについては、
**Localを優先しない**(測っていないものを「十分」と言わない)。

Local Runtimeは`LocalModelProvider`がOpenAI互換HTTPで話すため、
Ollama固定ではない(§43は既に満たしている)。

---

## 10. Task Routing(§14)

Provider全体ランキングを持たない。`(task, model)`ごとの品質を持つ。
MVPでは`TaskProfile`に

* `requires_strict_schema: bool`
* `sensitivity: LOCAL_ONLY / CLOUD_ALLOWED`
* `latency_budget_ms`

を持たせ、品質スコアはBenchmark接続後に足す。

---

## 11. Privacy(§25・§26)

`TaskProfile.sensitivity`を**型として今入れる**。値は現状すべて
`CLOUD_ALLOWED`だが、`LOCAL_ONLY`のTaskが将来出たときに、
Routerが構造的に外部送信を選べないようにするための土台である。

**現状Privacy Policyは未完成**であり、健康情報等の判定は行っていない。
TECH_DEBTへ明記する(§26)。

---

## 12. Retry Safety(§16)

Routerは**純粋推論(pure inference)のみ**をfallback対象にする。
副作用を伴う実行は`ForgeTask`に存在しない(現状すべて推論)。
将来Tool Useを足す場合、**副作用Taskは`retryable=False`として
Router契約から外す**——同一Requestの別Provider再送で二重実行が
起きるのを、設計として防ぐ。

無限fallback防止(§20): 1論理Taskにつき`attempted`集合を持ち、
同じProviderを二度試さない。retry予算とlatency予算の**両方**で打ち切る。

---

## 13. 検討して**採用しなかった**案

| 案 | 却下理由 |
|---|---|
| 並列hedging(§29) | Quota倍消費・cost倍・privacy露出増。MVPでは逐次。Benchmark後に再検討 |
| API Key Rotation | §23で明確に禁止。Rate Limit回避目的の設計はしない |
| 定期Health Check生成Request | §30。Quotaを自分で食う。実利用結果からのみ更新する |
| Provider/Model二階層を今入れる | 使われない抽象が増える(§3.1の再来)。型だけ用意し実装はMVP後 |
| Quota UNKNOWN を無制限扱い | §46で禁止。枯れているのに選び続ける |
| Mockを最終fallback | §22で禁止。偽のToolを本物として渡すことになる |
| Provider名をユーザーへ出す | §2。Conversation UXは変えない |

---

## 14. MVP Slice(§39)

**API Key不要で完全に検証できる範囲**を最初に作る:

1. `ErrorKind` + 例外→分類
2. `ProviderState`(health / quota / 統計)
3. `CircuitBreaker`
4. `AIRouter`(候補列挙 → 除外 → 並べ替え → 逐次実行 → 状態更新)
5. `TaskProfile`(strict schema / sensitivity / latency budget)
6. Test Double(quota切れ / timeout / auth / 5xx / invalid / 正常)
7. `/converse`・`/generate`をRouter経由へ**実際に配線する**

**7を必ず含める。** これが無ければ§3.1の問題を繰り返す。

---

## 15. Migration

現行`ModelGateway`は**残したまま**、Routerがその上位に立つ。
`ModelGateway`は「Task→Provider名の解決 + 計測」という役割に縮小し、
健康状態・Quota・Circuit BreakerはRouterが持つ。

既存の`provider`明示指定(HTTP API・テスト)は**そのまま動く**:
明示指定はRoutingを迂回する(§既存契約の維持)。Mockも明示指定時のみ。

---

## 16. Tests(§40の12ケース)

すべてTest Doubleで実施し、**API Keyを必要としない**。
逐次fallback・状態遷移・予算打ち切り・Mock除外を含む。

---

## 17. 残るリスク(正直な申告)

1. **実APIで一度も検証していない**。Gemini無料枠の実挙動(429の
   ヘッダ内容、reset時刻の有無)は未確認。分類は文字列マッチに
   依存しており、実際のメッセージ形式が違えば`UNKNOWN`へ落ちる。
2. **Quota推定は実装しない**。`ESTIMATED`は型として持つが、
   使用履歴からの推定ロジックはMVPに含めない(測っていない推定を
   Routingへ使うと、外れたときに原因が分からなくなる)。
3. **並行実行時の競合**(§47-27)。`ProviderState`はプロセス内
   メモリで、複数ワーカーでは共有されない。`ConversationStore`と
   同じ既知の制限(TD41)である。
4. **Benchmark未接続**。Task別品質スコアは型だけで、値が無い。
   したがってMVPのRoutingは「品質」ではなく「可用性」で選ぶ。
   これを品質判断だと表現しない。

---

## 18. Conversation UXへの影響

**無い。** Routerは`/converse`の内側に隠れ、ユーザーへProvider名を
見せない(§2)。ただし§21の「品質劣化を隠さない」は守る:
全Cloud不可・Localも品質不足のとき、**偽のBUILDをしない**。
その判断はProduct側(Readiness / Confidence)が既に持っているため、
Routerは「使えるProviderが無い」ことを正直に返すだけでよい。
