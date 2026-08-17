# FORGE-ROADMAP R0 / R0.1 — 実施報告

2026-08-17 / branch `claude/forge-master-handoff-k46jns`
上位文書: `docs/PRODUCT-DIRECTION.md` / `docs/ROADMAP-TO-TARGET.md`

---

## 0. この報告が扱う範囲

| | 内容 | commit |
|---|---|---|
| R0 | Experienceを本番の3経路から記録する | `d065f58` |
| 011 §7 | CI(GitHub Actions) | `32087d5` `d206ac9` |
| R0.1 | AI連携の失敗を直す(Provider内Model fallback) | `736a5cd` |

---

## 1. R0 — Experienceを本番から記録する

### 1-1. 何が問題だったか

Product Direction §7 が「完成扱いしてはならない」と名指しした状態:

> ExperienceStore はあるが **Production から記録されない**

実測で本番からの呼び出しは **0件**だった。

### 1-2. 根本原因(局所Patchにしないために先に考えた)

同じ形の失敗が**4回**続いている。

```
ModelGateway          (TD59)        作ったが本番から呼ばれない
classify_correction   (007 §10)     作ったが本番から呼ばれない
/generate・/update    (010 Phase B) Routerを迂回していた
ExperienceStore       (TD64)        作ったが本番から呼ばれない
```

共通しているのは「**呼び出し側が忘れずに呼ぶ**」設計だったこと。
忘れずに呼ばれる保証が無いものは、忘れられる。

Unit Testはこの失敗を1つも捕まえなかった。`ExperienceStore`のテストは
21件あって全部通っていたが、**そのすべてがテスト自身で
`store.record(...)`を呼んでいた**。「呼べば動く」ことしか確かめて
いなかった。

### 1-3. 採った形

**記録地点を1箇所に置いた**——`AIRouter.generate()`。本番のAI呼び出しが
必ず通る唯一の入口であり、Phase Bの Anti-Bypass Regression がそれを
証明済みである。Endpointが増えても記録を書き忘れることが**できない**。

成功だけでなく**全Provider失敗も記録する**。成功だけ貯めると
「Providerは常に上手くいっている」という記録ができあがる。

### 1-4. 「時刻が3つに分かれている」問題

1回のAI呼び出しについて、事実が揃う時刻は3つある。

```
呼び出し直後   Provider / model / latency / fallback
生成の終わり   Validatorを通ったか
次のターン     利用者が承認したか、訂正したか   ← 一番価値がある
```

呼び出し時点で全部揃う前提にすると、**一番価値のある信号だけが永久に
記録されない**。Product Direction §5 が「正しさの根拠」として挙げた
User ACCEPTED / CORRECTED がまさにこれである。

したがって`ExperienceRecord.ref`(不透明な通し番号)で後から書き足す形に
した。

* `note_generation_outcome()` — Validatorの合否・repair回数
* `note_acceptance()` — 利用者の承認/訂正。**先に書かれた信号が勝つ**
  (後から来る弱い信号で「訂正された」を消さない)

会話の`accept`/`clarify`/`rewind`は、`ConversationStore`が
**前ターンの記録へ**書き足す。011 §5で型として分けたACCEPTED/UNKNOWNが、
ここで初めて本番の値として現れる。

### 1-5. 実機で見つけた実バグ

実Providerで確認したところ、記録が
`{"provider": "gemini", "model": ""}` になっていた。`GeminiProvider`
だけがModel名をprivate属性(`_model`)にしていてRouterから読めなかった。

Providerだけ分かってModelが分からない記録は、Model入れ替えの前後を
区別できず学習素材にならない。`model`プロパティを公開し、回帰テストを
追加した(未設定の汎用Cloud枠は対象外——呼べないものが名乗らないのは
矛盾ではない)。

### 1-6. 配線が置物でないことの確認

5箇所の配線を1つずつ外し、対応するテストが落ちること・戻すと通ることを
確認した。

**最初に書いた`/update`のテストは、配線を外しても通ってしまった。**
Routerの自動記録だけで条件を満たせていたためである。テストの方を直した。

### 1-7. 実機確認

実Gemini(`gemini-flash-latest`)で`/converse`を実行:

```json
{"provider":"gemini","model":"gemini-flash-latest",
 "structured_output_valid":true,"used_fallback":false}
```

利用者の発話が記録に含まれないことも確認した。Gemini側の503で失敗した
往復も記録されている(失敗の記録も動いている)。

---

## 2. 011 §7 — CI(GitHub Actions)

`.github/workflows/ci.yml`。初回実行(run #1)で3ジョブとも green。

```
backend + forge_ai (Python 3.11)   success
backend + forge_ai (Python 3.12)   success
frontend (Flutter analyze + test)  success
```

**実APIは呼ばない。** `FORGE_LIVE_TEST`を設定しないので
`test_live_api.py`は自分でSKIPする(010 Phase Iの既定)。CIにAPIキーを
置かないため、無料枠を消費せず(§38)、Secretが漏れる経路が最初から
存在しない(§14〜18の境界をCIでも保つ)。

Python 3.13を入れていないのは好みではなく、`requirements.txt`が書いて
いるとおり pydantic 2.7.4 / supabase 2.5.1 が3.13のwheelを出していない
ためである。

---

## 3. R0.1 — AI連携の失敗を直す

### 3-1. 症状

CEOが実際に使ったところ失敗した。再現したら **6回中6回失敗**。

```
試行: [gemini(provider_server_error), local(local_resource_error)]
除外: [mock: テスト専用のため自動選択しない]
```

### 3-2. 原因は3つ重なっていた

**(1) 環境** — 既定Modelが混んでいた。同時刻・同じ鍵・同じPayloadで
各3回の実測:

```
gemini-flash-latest        [200, 503, 503]   ← Forgeの既定
gemini-flash-lite-latest   [200, 200, 200]
gemini-3.5-flash           [200, 200, 200]
```

Google自身が「一時的だ」と言う503である
("Spikes in demand are usually temporary")。

**(2) 設計** — §20「同じProviderを二度試さない」を、一時的な失敗にも
当てていた。恒久的な失敗(鍵が無い・未実装)には正しいが、一時的な失敗に
当てると**混雑がそのまま「AIが使えません」になる**。

**(3) 設計** — `ProviderDefinition.models`は「診断とBenchmarkのため」
であり、Routingには使っていなかった。「別Modelなら通る」という事実が
実行へ反映される経路が無かった。

### 3-3. Provider Identityを増やさなかった理由

`gemini-flash-latest`と`gemini-flash-lite-latest`を別Providerとして
登録すれば、既存の巡回だけで解決する。**しかしそれは011 §1が禁じた形
である。**

`provider_id`はQuota・Circuit Breaker・Benchmark・Experience・
Provenanceの唯一の識別键である。同じ鍵・同じ枠を共有する2つを別
Providerにすると:

* 枠切れを片方で学習しても、もう片方が同じ枠へ突っ込む
* Circuit BreakerがModel単位になり、Provider障害を検出できなくなる
* Benchmarkの比較単位がずれる

**ModelはProvider Identityではなく、Provider内部の実行選択肢**である。
Providerの外から見た振る舞いは変えていない——Circuit Breakerには
「geminiが**全Modelで**失敗した」だけが伝わる。

実装は`SupportsDeadline`と同じ「任意のCapability」の形にした
(`app/ai/foundation/model_choice.py`)。`LLMAdapter`の契約は変えていない。

### 3-4. 実測して分かった、もう1つのこと

429の本文を読んだ:

```json
{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
 "quotaValue": 20}
```

**枠はModel単位で1日20回。** これを受けて`QuotaScope`を宣言として追加し、
`PER_MODEL`と**実測で分かっている**Providerに限り、枠切れでも別Modelへ
進むようにした。既定は`UNKNOWN`で**進まない**——分からないものを楽観側へ
倒さない(`QuotaStrategy.NONE`が「不明を無制限と扱わない」のと同じ姿勢)。

### 3-5. 文言も直した

枠切れと障害を同じ「しばらく待ってからもう一度お試しください」で案内
していた。1日単位の枠切れに対しては嘘になる(5分後も同じ結果)。
**打つ手が違うものを同じ文言で案内しない。**

### 3-6. 実機確認

```
修正前   /converse  0/6 成功
修正後   /converse  6/6 成功
         /generate  3/3 成功
```

配線を1つずつ外して対応するテストが落ちることを確認した。
**「枠が不明なら賭けない」の最初のテストは、配線を壊しても落ちなかった**
——候補が1つしか無いProviderで測っていたため偶然通っていた。テストの方を
書き直した。

---

## 4. 副次的に見つけたこと(未解消・判断待ち)

> **2026-08-17 追記(013で訂正)**: 以下2項は、初出時に**測った範囲より
> 広い主張**をしていた。013の独立監査で指摘を受けて測り直し、訂正した。
> 正確な記述は `docs/reports/FORGE-PRE-R1-INTEGRITY-GATE-013-report.md`
> §3・§5、および TECH_DEBT.md TD65 / TD66 / TD67 を参照。

### 4-1. Curated Domainの生成stageはAI呼び出し0回(→ TD65、013で解決)

~~Curated DomainはAIを1回も呼ばない~~ → **正しくは「生成stageが
AI Providerを呼ばない」**。会話(`/converse`)は`ConversationEngine`自身が
AIを呼ぶので、会話ステップのExperienceは残る(実測で確認)。

~~この経路はExperienceを1件も残さない~~ → **正しくは「生成物についての
Evidenceが残らない」**。

013で`GenerationRecord`(生成物単位のEvidence)を導入し、`source=curated`
として残すようにした。**Curatedを消さず、AIを無理に通さずに**閉ループへ
載せている。

### 4-2. Gemini無料枠(→ TD66 / TD67、013で証拠の範囲へ訂正)

~~Model 3つで1日60回が上限~~ → **推論であって実測ではない**。実測したのは
「観測した1 Modelの`quotaValue`が20」「`quotaId`が`PerProjectPerModel`」
の2点だけである。

~~コード変更は不要~~ → **設計上そうなっている、が正しい**。Groq等の実APIは
一度も呼んでいないので、接続時にコード変更が不要であることは未証明
(TD67)。

---

## 5. Product Direction §8 — 自己監査(7問)

| # | 問い | 答え |
|---|---|---|
| 1 | 生成アプリの品質を上げるか | **R0は直接は上げない**(測る足場)。**R0.1は上げる**——AIが呼べなければ品質以前である |
| 2 | Local AIが学習・利用できる構造か | **なる。** Task別・Model別に、Validator合否とUser ACCEPTED/CORRECTEDが揃った記録が貯まる |
| 3 | 片方のためにもう片方を後退させたか | **していない。** 既存の応答経路は変えていない |
| 4 | Template依存を増やしたか | **増やしていない**(Widget/Template追加0件)。ただし**既存のTemplate依存を1つ発見した**(TD65) |
| 5 | Production Pathへ本当に接続されたか | **された。** ExperienceStoreに触れずHTTP APIを叩くテストで確認。実Geminiでも確認 |
| 6 | Evidenceが残るか | **残る。ただし揮発する**(プロセス内メモリのみ)。Curated経路は013で解決(TD65) |
| 7 | 実装都合で最終目標を縮小したか | **していない。** 残件は下記のとおり明示する |

### 問題として報告するもの(§8「黙って目標を変更しない」)

1. **永続化していない** — プロセス内メモリのみ、上限1000件。再起動で
   消える。Dataset化(R6)には足りない。
2. **`ABANDONED`が一度も書かれない** — 会話の放棄を検出していないので、
   負例が`CORRECTED`しか集まらない。
3. **Privacy Policy(TD60)が未完成** — 記録項目は絞ってあるが、
   「入らない設計である」ことと「利用者に説明した」ことは別である。
4. ~~**Curated経路からEvidenceが取れない**(TD65)~~ → **013で解決**
   (`GenerationRecord`)。
5. **無料枠が足りない**(TD66) — 2つ目のProviderが要る。

---

## 6. テスト

```
backend/tests    1079 passed / 16 skipped
forge_ai/tests    521 passed
CI               3ジョブとも green
```

追加したテストファイル:

* `backend/tests/test_experience_wiring.py` — ExperienceStoreに触れずに
  HTTP APIを叩き、その結果として記録が増えることだけを見る
* `backend/tests/test_model_fallback.py` — Model fallbackの巡回条件・
  Provider Identityの不変・利用者への文言

いずれも「配線を外すと落ちる」ことを実際に確認済み。
