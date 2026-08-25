# FORGE-017A — Learning Contract Hardening + 016A-C / R2

2026-08-24 / branch `claude/forge-master-handoff-k46jns`
開始HEAD `c653ff2` → 終了HEAD（このcommit）

---

## 0. 一行で

017Aの指摘は**全て正しかった**。commit Bで作った契約には、
「教師データに嘘が混ざる」「事実を捨てる」「失効するIDを系譜に使う」
「内容ハッシュを外へ出す」という4つの穴があった。塞いだ上で、
残R1 HardeningとR2 Knowledgeまで進めた。

---

## 1. commitの一覧

| commit | 内容 | § |
|---|---|---|
| `b61b36d` | Revision training provenance | §1 |
| `d163e6f` | Feedback Event + Handle/EvidenceId/VersionToken分離 | §2・§3・§4 |
| `2db1fcd` | Learning Contract語彙 + Local Promotion Gate | §5・§6・§7・§10 |
| `a514a37` | Semantic Critic誤検知2件 + `/converse` Golden E2E | §14 |
| `e40c861` | Forge Knowledge + Intelligence Context Resolver | §8・§15 |

---

## 2. §1 — 由来不明/Test DoubleのRevisionが教師データになっていた

### 実際の欠陥

commit Bの`RevisionRecord.is_positive_example`は3条件しか見ていなかった。

```python
validator_passed and user_acceptance.is_positive and runtime != FAILED
```

`source`の既定は`UNKNOWN`なので、

```python
RevisionRecord(validator_passed=True, user_acceptance=ACCEPTED)
```

がそのままTraining Candidateになった。

**`TEST_DOUBLE`が特に悪い。** Mockの出力を教師にするとMockの癖を学ぶ。
テストは`mock` Providerで大量に走るので、**実運用よりテストの方が
「正例」を多く生む**状態だった。

生成側は013から`source.is_usable_for_training`を要求していた。
**同じ語彙を使いながら片方だけ緩い**——011 §5で一度踏んだ形である。

### 直した形

4条件へ揃え、`RevisionEvidenceStore.training_candidates()`を生成側と
対称に足した。全`GenerationSource`について**生成と変更の判定が一致する**
ことをテストで固定した（片方だけ条件が増減すると静かに嘘になる）。

### 破壊試験

`source`検査を外す → 5件FAIL。

---

## 3. §2 — Feedbackの時系列を捨てていた

### なぜ捨ててはいけないか

```
ACCEPTED → CORRECTED
             ↑ commit Bはここを捨てていた
```

`GenerationRecord.user_acceptance`は1つしか値を持てないので、**要約
としては**first-winsで良い。塗り替えると「その時点でどう扱われたか」が
消えるからである。

しかし**捨ててよいのは要約であって、事実ではない**。

「最初は良いと言ったが、使ってみたら直した」は、最初から`CORRECTED`
だったものと**まるで意味が違う**——前者は「一見よく見えるが実際には
外している」という、Local AIにとって最も価値のある系列である。
1つのfieldに潰すと区別できない。

### 直した形

`ArtifactFeedbackEvent`を**追記専用**で持つ。

```
event_id / artifact_evidence_ref / signal / sequence /
source / recorded_at / idempotency_key
```

`FeedbackEventLog`は`update`/`delete`を**持たない**（持っていないこと
自体をテストが見張る）。`FeedbackResult`に`summary_updated`を足し、
「事実は残したが要約は変えなかった」を表せるようにした。

`FeedbackSource`も足した。**`INFERRED`は教師信号に使わない**
——Forgeの推定を「利用者がそう言った」として学習すると、Forge自身の
思い込みを増幅する。

### 再送と再評価の区別

`idempotency_key`が一致したものだけを再送とみなす。**キーが無ければ
再送とみなさず追記する**——分からないものを「たぶん再送」へ倒すと、
本物の再評価が静かに消える（`CLAUDE.md` §3）。

---

## 4. §3・§4 — 1つのIDに3つの役目を持たせていた

### 分けた

| | 何のためか | 寿命 | Clientへ | Cloudへ |
|---|---|---|---|---|
| `ArtifactHandle.handle` | 評価を送り返す | 失効する | **出す** | **出さない** |
| `ArtifactEvidenceId` | Dataset Lineage | 記録に貼り付く | 出さない | 出す |
| `version_token` | 世代照合 | ハンドルと同じ | **出す** | **出さない** |

**ハンドルを系譜に使ってはいけない理由は2つある。**

1. **失効する。** プロセス再起動で消え、1000件超で古い順に捨てられる。
   系譜をこれで辿ると、失効した時点で切れる
2. **Bearer Capabilityである。** 持っている人が評価を書ける。Cloudの
   Learning Eventへ載せると、記録を見た人が誰でも評価を書き換えられる
   ——**用途が正反対**

`GenerationRecord` / `RevisionRecord`へ`uid`（永続ID）を足した。
**Storeが付ける**ので付け忘れが起きない。`ref`はStore内の位置でしか
なく、プロセスを跨ぐと別の記録を指す（1番は次のプロセスでも1番だが、
中身は別物である）。

### §4 指紋

commit Bは`document_fingerprint()`（salt無しsha256）をそのままClientへ
返していた。

* 内容が同じなら**誰が作っても同じ値**になる → 利用者を跨いだ突き合わせ
* 内容の候補が少なければ**総当たりで中身を言い当てられる**（「メモ」
  1画面のアプリなど、低entropyな生成物は実在する）

「hashだから本文は復元不能」は、この2点を無視した言い方だった。

世代照合に必要なのは「さっきと同じものか」だけなので、**内容と無関係な
ランダムtoken**にした。`ArtifactRegistry.register()`は**Documentを
受け取らなくなった**——見ないなら受け取らない。受け取れば、いつか誰かが
内容から何かを作る。

`document_fingerprint()`は内部専用として残した（消したのではなく、
用途を絞った）。

### 破壊試験

5round。2つ目の信号を捨てる/EvidenceIdへrefを載せる/tokenを固定値に
する/idempotencyを無視する/指紋をClientへ返す——全てFAILを確認。

---

## 5. §5・§6・§10 — 契約をEvidence Store型に縛らない

### §5 Event種類

commit BまでのLearning Event V1は`generation`/`revision`/`ai_call`/
`benchmark`の4種だけだった。これは**いま実装がある型を並べただけ**で、
Growing AIの構想から勝手に縮小している。

**実装が無いものを「未実装」として持つのと、構想から消すのは違う。**

`LearningEventType`を構想どおりの広さ（`feedback`/`regeneration`/
`build`/`compile`/`test`/`validation`/`runtime`/`crash`/`tool_result`）
で定義し、`is_emitted_today`で「いま実際に作れるか」を分けた。
テストが**構想にあった種類が消えていないこと**を見張る。

### §6 Task語彙

`ForgeTask`はAI Routing / Benchmarkの語彙で、4値しかない。
`flutter.build`や`runtime.render`は**AIを呼ばない**ので`ForgeTask`に
なりようがないが、Learning Eventとしては事実である。

`ForgeTask`へ無理に足すと、**Providerが要らないTaskがRouting表に並ぶ**。

`LearningTaskId`（`namespace.name`、自由文禁止）を足し、
**全`ForgeTask`がmappingされていることをテストで強制**した。
`ForgeTask`へ値を足した人がmappingを忘れると、そのTaskのEventだけ
静かにLearning側から消えるので、その書き忘れを見張る。

対応が無ければ**既定値へ落とさず例外**にする。落とすと、書き忘れたTask
が全部同じラベルに潰れて後から見分けられない。

### §10 scope

`scope = global | app | personal`だけでは、「誰の知能を改善するか」と
「Cloudへ出してよいか」が1つの値に混ざる。

`IntelligenceScope` / `DataResidency` / `ContributionTarget`へ分けた。
**「Appの知能を改善するが、内容はCloudへ出せない」は1軸では表せない。**

既定は`LOCAL_ONLY` / `NONE`。

---

## 6. §7 — Local Firstの矛盾を Quality Gate で解消

### 矛盾していた

Architectureは「Qualified Local → Local」と書きながら、実装側の説明は
「Local優先はBenchmark順位が同点のときだけ」だった。

**同点のときだけ効く優先は、実質Local Firstではない。** Cloudが1点
高ければ毎回Cloudが選ばれるので、Localは永久に使われない。

### しかし過去の教訓も正しい

`AIRouter._order()`のdocstringに、実装して考え直した記録がある。

> Local優先は根拠が無い。Benchmarkが無いのにLocalを優先するのは、
> **測っていない品質を賭けてQuotaを節約している**だけで、Product
> Qualityを壊しうる。

### 解

**Best Score Wins をやめ、Quality Gate にした。**

```
❌ Local 0.91 vs Cloud 0.93 → 毎回Cloud（Localは永久に使われない）
✅ Localが「製品として通用する水準」を満たすなら、Cloudが上でもLocal
```

`LocalPromotionGate`が実測から判定する。全条件（capability /
benchmark実測 / 品質水準 / schema成功率 / latency / 件数 / 鮮度 /
dataset同一性）を満たさなければ通さない——**1つでも欠けたら通さない**
のは、「だいたい満たしている」で通すと何が理由で通ったのか後から
分からなくなるからである。

`AIRouter._order()`から**実際に呼ぶ配線まで入れた**。

### いま何件通るか

**0件である。** Localのbenchmark記録が1件も無い（実測）。つまりこの
配線は**今は何も変えない**。データが入れば効き始める——配線済み・
データ待ちの状態にしてある。

### Gateは順位を付けない（§8）

`rank`/`order`/`bind`等のメソッドが生えていないことをテストで固定した。

---

## 7. §8・§15 — Knowledge と Resolver

### TD69の再発防止

`design_language.knowledge_entries()`は014から存在したが、**本番から
1度も呼ばれていなかった**。「作ったが本番から呼ばれない」の5例目。

型を作るだけで終わらせず、**本番のHTTP経路が実際に通る**形にした。
`GenerationRecord.knowledge_references`に

```
design_role.metric.primary@v1
```

が残ることを、`/generate`のHTTP往復で確認している。

### scope を最初から持つ

`app_id`はコードに**1箇所も存在しなかった**（017 Reviewの実測）。
**ここが最初の1箇所である。**

後から付けられない。Entryを1件でも作った後に遡ると、既存の全Entryを
人間が判断し直すことになり、判断できないものは`UNKNOWN`になって結局
作り直しになる。

境界は**構造**である（「返さない運用」ではない）。

| 求める範囲 | 返るもの |
|---|---|
| `GLOBAL` | Globalのみ |
| `APP` + `app_id` | そのApp + Global |
| `PERSONAL` | Personal + Global |

**AppはGlobalを見られるが、GlobalはAppを見られない。** 逆向きを許すと、
あるAppの知識が全利用者の生成へ効く（017 §18）。

### Resolverを AIRouter へ詰め込まない

`AIRouter`は既にRouting・Circuit Breaker・Quota・Latency予算・
Experience記録・Local昇格を持っている。ここへ知識検索まで入れると
神クラスになる。

```
IntelligenceContextResolver → resolved context → AIRouter → Provider
```

**順番も重要である。** 知識はProvider選択の**前**に決まっていなければ
ならない——CloudとLocalで渡す知識が変わると、「同じ問いに同じ知識で
答えた」という比較ができず、Benchmarkの前提が崩れる。

### 全部渡さない

33件中12件。選択肢が多いとAIは外すし、Local Modelの文脈長を無駄に
使う（014 §7で`DESIGN_CHOICE_AXES`を絞ったのと同じ理由）。
会話ステップには渡さない——何を作るかを聞いている段階で、どう見せるか
はまだ決めていない。

---

## 8. §14 — Semantic Critic の誤検知2件（両方とも再現してから直した）

### 8.1 単一であるべきroleを文書全体で数えていた

```
一覧画面に metric.primary が1つ
詳細画面に metric.primary が1つ
```

という**正しい設計**が「metric.primaryが2個ある」として弾かれていた。
指摘文自身が「metric.primaryは**画面で**1つだけにする」と書いているのに、
数えるのは文書全体だった。

**画面が増えるほど誤検知が増える**ので、複数画面のアプリを作るほど
Criticが役に立たなくなる形だった。

画面ごとに数え、指摘文に画面名を入れた（どこを直せばよいか分かるように）。
同一画面の重複は依然として`high`のまま。

### 8.2 finance と state の併用を無条件に誤りにしていた

家計簿アプリは**正当に両方を使う**。

```
finance.expense … 支出（お金が出ていく向き）
state.danger    … 予算を超えた（状態が悪い）
```

これは兼用ではなく、**別々のことを別々の語彙で言っている**——015 §9が
求めた姿そのものである。それを弾いていた。

本当の誤りは「支出を危険として塗る」こと、つまり**同じ値**に両方の
意味を持たせることである。Widgetは`value_field`等で「どの値を見せて
いるか」を持っているので、そこで判定するようにした。

**値の結び付きが分からないWidgetは判定しない**——分からないものを
誤り側へ倒すと、また誤検知になる。

### 8.3 `/converse` Golden Finance E2E

これまでのGolden E2Eは`/generate`だけを通っていた。**実機で利用者が
実際に通るのは`/converse`**であり、そちらは

```
ConversationEngine → build_brief（Forgeが書いた説明文）→ Pipeline
```

と1段挟まる。ここで意味が痩せると、`/generate`は通るのに`/converse`は
通らないという**「実際に使う方が壊れる」**状態になりうる。013で
`/generate`と`/update`の両方にRouter迂回があったのも「片方だけ直して
終わりにした」ことが原因だった。

会話からBUILDへ到達し、主KPIが立ち、Evidenceが残り、artifactハンドルが
返ることまでを固定した（6件）。

---

## 9. 配線破壊試験の一覧（全24round）

| # | 外したもの | 落ちたテスト |
|---|---|---|
| A1 | Revisionの`source`検査 | 5件 |
| A2-1 | 2つ目の信号を捨てる | 2件 |
| A2-2 | `EvidenceId.to_dict`へ`ref`を載せる | 1件 |
| A2-3 | `version_token`を固定値にする | 4件 |
| A2-4 | idempotencyを無視する | 3件 |
| A2-5 | 指紋をClientへ返す | 2件 |
| A3-1 | `ForgeTask`へ値を足して対応を忘れる | 2件 |
| A3-2 | Event種類をStore4種へ縮める | import不能 |
| A3-3 | `DataResidency`の既定を`cloud_eligible`に | 1件 |
| A3-4 | 自由文を通す | 2件 |
| §7-1 | RouterがGateを見ない | 1件 |
| §7-2 | 未測定Localも昇格させる | 4件 |
| §7-3 | 品質水準を無視する | 3件 |
| C-1 | 画面ごとの集計を文書全体へ戻す | 3件 |
| C-2 | finance/stateを「同じ文書に両方ある」へ戻す | 3件 |
| C-3 | `/converse`から`artifact`を落とす | 1件 |
| D-1 | 本番がResolverを呼ばない（TD69の状態） | 1件 |
| D-2 | Global検索がPersonal/Appも返す | 4件 |
| D-3 | `to_dict`が本文を含む | 2件 |
| D-4 | `DRAFT`も検索に出す | 2件 |
| D-5 | `app_id`の必須検査を外す | 2件 |

**全roundで、外すと落ち、戻すと通ることを確認した。**

---

## 10. 検証区分

| 項目 | 区分 |
|---|---|
| Feedback往復・Knowledge到達（HTTP） | **実測**（`TestClient`、`mock` Provider） |
| 配線破壊試験 24round | **実測**（実際に外して落ちることを確認） |
| Critic誤検知2件 | **実測**（直す前に再現した） |
| Local Promotion Gate | **実測**（単体 + Router経由）。ただし**昇格するProviderは0件** |
| 実Cloud Providerでの往復 | **未検証**（実APIを呼んでいない） |
| Local Modelでの実生成 | **未検証・0回**（§9） |
| Flutter側 | **未検証**（この環境にSDKが無い。CI待ち） |

---

## 11. まだ無いもの（正直に）

* **Flutter側の👍ボタン。** Backendの口は揃ったが、利用者が押せる
  ボタンはまだ無い。`user_acceptance`が実データで埋まるわけではない
* **Learning Eventを実際に作って送る経路**（commit E）。契約と語彙は
  あるが、`LearningEvent`を組み立てるコードは無い
* **Consent / Sanitizer / Retention / Dataset Lineage**（commit E）
* **`RevisionRecord`を書く本番経路**（commit F）。型とStoreはあるが、
  `/update`から残す配線は無い
* **Local Base Model** — 実モデルでの生成は**0回**（§9）
