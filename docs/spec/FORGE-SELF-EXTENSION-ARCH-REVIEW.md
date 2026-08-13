# FORGE-SELF-EXTENSION-ARCH-REVIEW

FORGE-ARCHITECTURE-REVIEW-AND-IMPLEMENT-005 §31 への回答。
2026-08-12。現物のコード・テストを監査した上での批判的レビュー。

**結論を先に**: 構想の中核(Capability-first・User Correction Loop)は
採用する。ただし**「Capability自動追加」(§12)は現時点で採用しない**。
理由は §5 に詳述する。代わりに、同じ価値をはるかに低いリスクで得られる
Vertical Sliceを提案・実装する。

---

## 1. 現状Architecture(現物)

```
User発話
  ↓
ConversationEngine (LLM 1回/ターン)
  ↓
conversation_policy      ← 決定的。LLMを知らない
  ├ requires_confirmation
  ├ select_question
  ├ evaluate_readiness    (5値)
  └ resolve_action        ASK/BUILD/UPDATE/CONFIRM
  ↓ BUILD
PromptPipeline → CognitiveOrchestrator (13段)
  ↓
domain_resolution        ← Curated / Generated
  ↓
IRGenerator → solution_shape → ForgeLanguageCompiler
  ↓
Validator (最大3) / Repair (最大2) / Critic
  ↓
Flutter Runtime (Widget 19種)
```

規模: forge_ai 519 tests / backend 773 tests / Flutter 452 tests。

**重要な現物の性質**:

* `conversation_policy.py`はProviderもLLMも知らない純粋関数群。
* `ForgeLanguageCompiler`は決定的。AIはJSONを直接書かない。
* Widget Registryは**19種で固定**。Runtimeが知らないWidget typeは
  安全にFallback表示される。
* `ModelGateway`はProvider実装を一切importしない。

---

## 2. 構想との適合点

| 構想 | 現物の状態 |
|---|---|
| Conversation is the product | 既に成立。Policy層がUXを守っている |
| Local AIはConversation Engineを置き換えない | 既に成立(Providerは`LLMAdapter`の裏) |
| Deterministic Compiler | 既に成立。むしろ既に理想形 |
| LLM Proposal < Forge Policy | 既に成立(D67) |
| Capability-first | **未成立**。現状はEntity-first |
| Missing Capability検出 | **未成立** |
| User Correction Loop | **未成立** |
| Capability自動追加 | 未成立(かつ採用非推奨、§5参照) |

つまり**下半分(Compiler/Policy)は既に構想どおり**で、
足りないのは**上半分(Need → Capability)**である。

---

## 3. 構想の問題点(批判)

### 3.1 「Capability」の粒度が定義不能に発散する(§30-C)

構想の例示は `text` `number` `chart` `map` `notification` … と、
**入力型・データ操作・表示形式・外部連携が同一平面**に並んでいる。
これらは抽象度が違う。`number`は型、`chart`は表示、`notification`は
副作用を伴うOS機能である。同じRegistryに入れると、

* 依存関係(chartはnumberを要求する)を表現できない
* 危険度が混在する(numberは安全、notificationは権限が要る)
* 粒度の議論が永久に終わらない(§30-C)

**修正案**: Capabilityを**1つの平面にしない**。3層に分ける。

```
DataCapability     : 何を記録するか   (text/number/date/choice/bool)
ViewCapability     : どう見せるか     (list/card/grid/chart)
EffectCapability   : 外へ何をするか   (share/notify/http/camera/location)
```

EffectCapabilityだけが安全審査の対象。Data/Viewは安全。
この分割で§30-F(security)と§30-C(granularity)が同時に片付く。

### 3.2 Capability不足を「AIが埋める」のは順序が逆(§12)

現物のWidget Registryは19種で、**Runtimeが実装を持っている**。
`map`が無いのはAIの能力不足ではなく、**Flutter側に地図Widgetが
存在しない**からである。ここでAIにCapabilityを生成させると、

* Dart実装の生成 → Flutterの再ビルドが必要 → 実行中アプリへ反映不可
* Web/iOS/Androidで挙動が違う → Sandbox検証が3重に必要(§30-G)
* 生成コードの権限昇格リスク(§30-F)

**そもそもFlutterは動的コード実行ができない**(Web/AOT両方で
`dart:mirrors`不可、コード生成後の再コンパイルが必須)。
つまり構想§12の「Capability自動追加」は、**現行Runtime構成では
物理的に成立しない**。仮に成立させるなら、Forge Language側に
インタプリタを持つ(=Widget DSLの拡張)しかなく、それは
Widget Registryを19種から動的に増やす話であり、
**Validator・Runtime・Registryの三重同期を毎回AIに任せる**ことになる。
TD37(Registryへの登録漏れで4種のWidgetが描画不能だった実バグ)を
踏まえると、これを自動化するのは危険度が高すぎる。

**結論**: §12は**採用しない**。代わりに§7の
「Missing Capabilityを明示的に検出して、ユーザーへ返す」までを
実装する。ここまでが今のRuntimeで安全に成立する上限である。

### 3.3 「違う」をTraining Signalにするのは今は早い(§10, §30-O/P)

`prompt → 正解JSON`より価値がある、という主張は正しい。だが、

* ユーザー自身も正解を知らない(§30-E)。「違う」の後の要求が
  最初の要求と矛盾することがある
* 「違う」が何に対してかが不明(§30-D)
* Privacy同意の設計が未着手(§30-P)

**修正案**: Training Datasetへは**一切入れない**。
User Correctionは**その会話の中でNeed Modelを更新するためだけ**に使う。
記録するとしても、匿名化された`correction_type`(下記)の集計のみ。

### 3.4 「違う」の分類(§30-D)への回答

構想は分類方法を示していない。**Forge側が仮説を出しているのだから、
仮説の"どの部分"が否定されたかで分類できる**:

```
SolutionHypothesis = { data: [...], view: ..., effects: [...] }
                          ↓ ユーザーが否定
CorrectionTarget = DATA | VIEW | EFFECT | PROBLEM
```

`PROBLEM`(そもそも困りごとの理解が違う)だけは会話を巻き戻す。
他3つはHypothesisの該当部分だけを差し替える。これなら
「違う」の曖昧さを、**Forgeが出した仮説の構造**で受け止められる。

---

## 4. Failure Modes / Risks

| # | Failure | 対応 |
|---|---|---|
| F1 | Capability爆発(§30-A/B) | 自動追加を採用しない。Registryは人手管理 |
| F2 | 「違う」ループが終わらない(§30-L) | 既存のStrategy Escalationを再利用。仮説も3回で打ち切り |
| F3 | AIが存在しないCapabilityを提案(§30-K) | Registryに無いものは`MISSING`として扱い、実装済みと偽らない |
| F4 | Latency悪化(§30-N) | Multi-Candidateは採用しない(下記§6) |
| F5 | 危険Capability要求(§30-Q) | EffectCapabilityは既存のCONFIRM Policyへ直結 |
| F6 | 縮退の勝手な実行(§34) | 既存の`SHRINK_SOLUTION`は理由付き記録が必須。仮説提示を挟む |

---

## 5. 採用しなかった案と理由

| 案 | 却下理由 |
|---|---|
| **Capability自動生成(§12)** | Flutterが動的コード実行不可。Registry/Validator/Runtimeの三重同期をAIに任せることになりTD37の再来。**物理的に成立しない** |
| **Extension SDK / Sandbox(§13)** | 上記が成立しない以上、置き場所だけ作っても空の抽象化になる |
| **Multi-Candidate + Critic(§19-20)** | Local実測が1回も無い現状で導入すると、latencyだけ増えて精度改善が測れない。**Benchmarkの後**でしか判断できない |
| **RAG(§18)** | 「考える材料を返す」方向性は正しいが、現状Curated 7定義しか知識源が無い。RAGを入れる前に、その7つが実際に使われているかの実測が先 |
| **User FeedbackのTraining投入(§10)** | Privacy同意設計が未着手。§30-O/Pが未解決 |

---

## 6. 推奨Architecture(修正後)

```
User発話
  ↓
ConversationEngine ─────────────┐
  ↓                             │
NeedModel                       │ 既存(無変更)
  ↓                             │
conversation_policy ────────────┘
  ↓
CapabilityResolver          ← 新規(薄い)
  ├ 必要Capabilityを3層で列挙
  ├ Registryと突合
  └ MISSING を検出
  ↓
  ├ MISSINGなし → 既存BUILD経路(無変更)
  └ MISSINGあり → SolutionHypothesis
                     ↓ 会話の1ターンとして提示
                  User Correction
                     ↓ CorrectionTarget で分類
                  NeedModel更新 → 再評価
```

**要点**: 既存経路に**一切触れない**。MISSINGが無ければ今と同じ。
Capability Registryは**人手管理の静的テーブル**(Widget Registry 19種と
1:1で対応)。AIはRegistryを**読むだけ**で、書き換えられない。

---

## 7. Vertical Slice(§32)

構想の推奨どおり、以下までを実装する:

```
Missing Capability Detection
  → Solution Hypothesis
  → User Correction
  → Revised Capability Spec
```

`Capability Registry / Extension Generation / Sandbox / Promotion`へは
**広げない**(§5の理由により、広げても実行できない)。

---

## 8. テスト戦略

* CapabilityResolverは純粋関数 → LLM無しで単体テスト
* §33の実例(釣果を地図で → 「違う、色を濃く」→ heatmap)を
  Golden Conversationとして固定
* 既存50セッションに対して**MISSINGが誤検出されない**ことを回帰確認
  (既存経路を壊していないことの担保)

---

## 9. Migration Plan

1. Capability Registry(静的、Widget Registry 19種と対応)
2. CapabilityResolver(Need → 必要Capability → MISSING検出)
3. SolutionHypothesis型 + 会話ターンとしての提示
4. CorrectionTarget分類 + NeedModel更新
5. Golden Conversation追加

各段階で既存テスト(1744件)がgreenであることを条件とする。

---

## 10. Production投入可否(§36-17への先出し回答)

**Self-Extension(Capability自動追加)は投入すべきでない。**
物理的に成立しないため、投入以前の問題である。

**Missing Capability Detection + User Correction Loopは投入可**。
既存経路に触れず、MISSINGが無ければ現状と同一挙動であるため、
リスクは「MISSINGの誤検出」に限定され、それは回帰テストで抑えられる。

---

## 11. 実装結果(2026-08-13追記)

§7のVertical Sliceを実装した。実体は
`backend/app/ai/runtime/capability.py`、テストは
`backend/tests/test_capability.py`(28件)。

### 実装したもの

| §9のMigration Plan | 状態 |
|---|---|
| 1. Capability Registry(静的、3層) | 完了。22定義(実装済み9 / 未実装13) |
| 2. CapabilityResolver(MISSING検出) | 完了。`detect_capabilities` / `missing_capabilities` |
| 3. SolutionHypothesis + 会話ターン | 完了。`ConversationEngine.step()`へ接続済み |
| 4. CorrectionTarget分類 + 更新 | 完了。DATA/VIEW/EFFECT/PROBLEM/ACCEPTED/UNCLEAR |
| 5. Golden Conversation | 完了。§33(釣果→地図→「色を濃く」→heatmap) |

### 実装して分かったこと(設計の修正)

**安全判定とCapability判定の順序を決める必要があった**(§6には書いて
いなかった)。50セッションを実際に流したところ、MISSINGが出たのは3件
(`schedule_shared`・`share_1`・`risky_1`)で、いずれも共有要求だった。
これらは既存のCONFIRM Policyが捕まえている——Capability層も割り込むと、
確認と仮説が二重に出て会話が壊れる。

そこで`has_buildable_gap()`を追加し、**MISSINGがEffectだけの場合は
会話に割り込まない**ようにした。結果として、既存50セッションの挙動は
**1件も変わらない**(回帰テストで固定済み)。§6の「MISSINGが無ければ
今と同じ」という要件は、実際には「Data/ViewのMISSINGが無ければ今と同じ」
だった。

**訂正の再提示をどう1回に抑えるか**も、実装して初めて具体化した。
既存の`asked_question_keys`(同じUnknownを繰り返し聞かない仕組み)へ
`capability_gap:view.map`のようなkeyを入れることで解決した。訂正で
不足が`view.heatmap`へ変わると別keyになるため、訂正後の仮説はちゃんと
1回だけ提示される。上限3回でF2(「違う」ループ)も塞がる。

### §10(Production投入可否)への回答は変えない

Missing Capability Detection + User Correction Loopは投入可。
Self-Extension(Capability自動追加)は§5のとおり投入しない。

### 残った正直な制限

* Effect Capabilityは**確認は取るが実装が無い**(共有・通知・カメラ等)。
  確認文を「できないこと」に合わせて書き換えるのは指示書001 §4で定めた
  CONFIRMの意味を変えるため、このSliceの範囲外とした(TD55)。
* `detection_keywords`は手書きの固定リストである。検出漏れは「今までどおり
  の経路」に落ちるだけだが、言い回しによっては地図要求を見逃す。
* Registryを増やす際はValidator・Runtime・`capability.py`の3箇所を同時に
  更新する必要がある。テストが機械的に検出できるのは`capability.py`側の
  嘘(`supported=True`なのにWidget型が存在しない等)だけである。
