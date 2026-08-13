# FORGE-SELF-EXTENSION-ARCH-REVIEW-v2

FORGE-USER-GUIDED-SELF-EXTENSION-006 §51 への回答。2026-08-13。
現物のコード・テストを再監査した上での批判的レビュー(第2版)。

**前回(v1)との関係**: v1を撤回はしない。v1のリスク指摘は今も有効である。
ただし**v1は問いの立て方を間違えていた**。§2に詳述する。

---

## 0. 結論を先に

1. **v1の技術的事実は正しい**。Flutterは実行中に新しいDart Widgetを
   注入できない。これは今も変わらない。
2. **v1の結論は誤りだった**。「Runtime Hot Plugが不可能」から
   「Self-Extensionは成立しない」を導いたのは飛躍である。
   指示書§4の指摘どおり、Goal 1とGoal 2を混同していた。
3. **再監査で、v1が見落としていた事実を見つけた**。Forgeに足りないのは
   Widgetの種類ではなく、**データ側のPrimitiveの一般性**である(§3)。
   ここを直すと、新Capabilityの多くが**コードではなくデータ**になる。
4. したがってSelf-Extensionは、**Declarative Capability Definitionの
   生成**という形で成立しうる。任意コード生成は依然として採用しない。
5. ただし**最優先はSelf-Extensionではない**。指示書§53のとおり、
   現行のUser Correctionは状態を持っておらず、「違う」を正しく
   保持できていない。ここを直すのが先である(§8で実証する)。

---

## 1. Product Goalの再定義

Forgeの目標は、次を成立させることである:

```
ユーザーが欲しいものを話す
  → Forgeが必要な能力を理解する
  → 今のForgeで作れるか確認する
  → 作れないなら、不足を認識し、仮説をユーザーへ返す
  → ユーザーの「そう」「違う」で仕様が育つ
  → Forgeが安全な方法で自身の能力を増やす
  → 以前は作れなかったToolを作れるようになる
```

**この文のどこにも「実行中にDartを注入する」とは書かれていない。**
v1はここを読み違えた。

---

## 2. 「Self-Extension」の定義(v1の誤りの所在)

v1は暗黙に、Self-Extensionを次の1種類として扱っていた:

> 実行中のFlutterアプリへ、AIが任意のDartコードを書き、即時実行する

この定義なら「不可能」は正しい。しかしこれは**Goal 1**であって、
Product GoalであるGoal 2ではない。

本レビューでは、Self-Extensionを次のように定義する:

> **Forgeが、自身では表現できない要求を認識し、その仕様をユーザーとの
> 会話で確定し、安全な検証を経て、以後その要求を表現・生成・描画・
> 使用できるようになること。**

「即時であること」も「Dartであること」も定義に含まれない。

### v1のどこが正しく、どこが誤りだったか

| v1の主張 | 判定 |
|---|---|
| Flutterは動的コード実行不可 | **正しい**(再確認済み) |
| 任意コード生成→Core直接注入→即本番実行 は危険 | **正しい**。今回も採用しない |
| Registry/Validator/Runtimeの三重同期リスク(TD37) | **正しい**。ただし対象はDartコード追加に限る |
| Capability == Widget として整理してよい | **誤り**。§4で修正する |
| ゆえにSelf-Extensionは物理的に成立しない | **誤り**。Goal 1にしか当てはまらない |
| Capability Registryは人手管理のみ | **部分的に誤り**。Trust Levelで分ければ生成物も置ける(§10) |

---

## 3. 再監査で見つけた、v1が見落としていた事実

これが本レビューで最も重要な発見である。

### 3.1 `bar_chart`は集計しない

`frontend/lib/json_ui/widget_registry/widget_registry_v1_6.dart:81`
`buildBarChart()`は、**Record 1件につき棒1本**を描く。
`valueField`/`labelField`はRecordのFieldをそのまま棒の値・ラベルへ
写像するだけで、**グループ化も集計も行わない**。

### 3.2 Runtimeに派生状態の仕組みが無い

`lib/json_ui/renderer/forge_runtime_state.dart`を調べた。
`derived` / `computed` / `aggregate` / `groupBy`に相当する機構は
**1つも存在しない**。State は保存された値をそのまま持つだけである。

### 3.3 したがって「heatmapが無い」は誤診である

§29の指摘どおりだった。「よく釣れる場所ほど色を濃く」に本当に
足りないものを分解すると:

| 必要なもの | 種別 | 現状 |
|---|---|---|
| 場所ごとにRecordをまとめて件数を数える | **データ変換** | **無い** |
| 数値の大小を色の濃さへ写像する | **表示パラメータ** | 無い(が既存描画の拡張で足りる) |
| 地理座標を平面へ投影して描く | **描画/Native** | 無い(本当に新規実装が要る) |

v1は3つをまとめて「view.heatmap が無い」と1語で扱っていた。
その粒度では、**何を作れば解決するのかが分からない**。

### 3.4 ここから導かれる設計上の含意

不足の内訳を見ると、**新しい描画の実装が要るのは地理描画だけ**である
(4つとも未実装である点は変わらない。違うのは種類である)。
1番目(集計)は汎用のデータPrimitiveであり、**一度作れば**
「場所ごとの釣果数」「カテゴリごとの支出合計」「月ごとの平均体重」
が**すべて既存の`bar_chart`で描ける**ようになる。

つまり:

> **Forgeに足りないのはWidgetの種類ではなく、データ側Primitiveの
> 一般性である。Widgetを1つ足すと1つの表現が増えるが、集計Primitiveを
> 1つ足すと表現の族が増える。**

v1が「Self-Extensionは成立しない」と結論したのは、
**Widget粒度でしか不足を数えていなかったから**である。
指示書§3-Bの「現在のWidget Registryの粒度自体がSelf-Extensionを
不必要に難しくしていないか」という問いに対する答えは、**イエス**である。

---

## 4. Capability Model(Capability ≠ Widget)

v1の Data / View / Effect 3層は、単一平面よりは良かったが不十分だった。
§6の指摘どおり、計算・集計・変換・条件・関係の置き場が無い。

本レビューでは次を採る。**Semantic Capability**(ユーザーの意味)と
**Runtime Primitive**(実行できるもの)を分離する。

```
User Need
   ↓
Semantic Capability          意味。ユーザー語彙に近い
   ↓  decompose
Runtime Primitive            実行単位。5種類
   ↓  bind
Forge Language / Widget      具体的な出力
```

Runtime Primitiveの種別:

| 種別 | 意味 | 安全性 | 例 |
|---|---|---|---|
| `DATA` | 何を保持するか | 安全 | text / number / date / choice / bool |
| `TRANSFORM` | 保持した値から別の値を導く | 安全(純粋関数) | aggregate / filter / sort / derive |
| `VIEW` | どう見せるか | 安全 | list / grid / bar_chart / tabs |
| `ENCODING` | 値を視覚属性へ写像する | 安全 | length / color_intensity / position |
| `EFFECT` | Forgeの外へ影響する | **要審査** | share / notify / camera / location / http |

**`TRANSFORM`と`ENCODING`はv1に存在しなかった層である。**
この2つが無かったために、集計も濃淡も「Widgetが無い」としか
言えなかった。

Effectは§6の指摘どおり性質が違うので、さらに区別する:

* `EFFECT/OUTBOUND` — 共有・送信・HTTP(データが外へ出る)
* `EFFECT/DEVICE` — カメラ・マイク・位置(OS権限が要る)
* `EFFECT/IRREVERSIBLE` — 削除・支払い(元に戻せない)

---

## 5. Self-Extensionの分類と、現行Runtimeでの成立可否

指示書§3の分類に沿って、**現物に照らして**判定する。

| 種別 | 定義 | 現行Runtimeで成立するか |
|---|---|---|
| **A. Composition** | 既存Primitiveの新しい組み合わせ | **成立する。Coreの変更すら不要** |
| **B. Declarative** | 新Capabilityを定義データとして表現 | **条件付きで成立**(§6) |
| **C. Build-Time** | 生成→検証→次Buildで獲得 | 成立しうるが今回は着手しない(§14) |
| **D. Service** | UIでなくサービスとして実現 | 成立するがBackend側の話。今回対象外 |
| **E. Native/Privileged** | OS権限を伴う | **仕様生成は可。自動有効化は不可**(§12) |

**採用順序**: A → B → (計測後に) C。
D/Eは仕様の生成までに留める。

---

## 6. Declarative Extensionが成立する条件(と、しない条件)

Bが成立するのは、**新Capabilityが既存Primitiveの合成として表現でき、
新しい描画コードを必要としない場合**に限る。

* **成立する例**: 「場所ごとの釣果数を棒グラフで」
  = `TRANSFORM/aggregate(group_by=location, agg=count)`
  + 既存 `VIEW/bar_chart`。
  **必要な新規Dartは`aggregate`のみで、しかもそれはCapabilityごとに
  増えない**(一度作れば族全体が使える)。
* **成立しない例**: 「地理座標を投影した地図」
  = 新しい描画そのもの。定義データでは表現できない。
  これは正直に「作れない」と言うべき領域である。

したがってDeclarative Extensionは**万能ではない**。
「定義データを書けば何でも増える」という設計にはしない。
**Runtime Primitiveの集合が上限を決める**。これは意図的な安全弁である。

---

## 7. Product SpecとPlatform Capabilityの境界(§37)

これはv1に無かった概念で、Self-Extensionの成否を分ける。

| | Product Spec | Platform Capability |
|---|---|---|
| 何を決めるか | このToolが何を保存し、どう見せ、どう操作するか | Forge自体が技術的に何を表現・実行できるか |
| 誰が決めるか | **ユーザー**(会話) | **Forge**(Policy + 検証) |
| 変更頻度 | 会話のたび | まれ |
| 「違う」の行き先 | ほぼここ | 例外的にここ |

**User Correctionの大半はProduct Specの修正であり、Platform Capabilityを
増やす必要は無い。** §36の「地図を青くして」はProduct Spec、
「場所ごとの集計」はPlatform Capabilityである。

この判定を誤ると、§27のCapability乱立(`blue_map`)が起きる。

判定規則(§28の「独立させる条件」への回答):

新しいPlatform Capabilityとして独立させるのは、次を**すべて**満たす場合のみ:

1. **再利用可能**: 少なくとも2つの無関係なDomainで要求されうる
2. **合成不能**: 既存Primitiveの組み合わせでは表現できない
3. **パラメータ化不能**: 既存Capabilityの引数追加では足りない
4. **独立テスト可能**: それ単体で正しさを定義できる
5. **境界が明確**: 権限境界・Runtime境界をまたがない

1つでも欠ければ、それはProduct Specか、既存Capabilityの拡張である。

---

## 8. Stateful User Correction(現状の実測と設計)

### 8.1 指示書§10〜§12の指摘は、現物で確認して**すべて正しかった**

再監査結果:

```
$ grep -rn "classify_correction|revise_hypothesis" --include=*.py .
→ tests/test_capability.py からのみ。**production codeは1箇所も呼んでいない**
```

`ConversationSession`のフィールドは
`session_id / turns / created_at / asked_question_keys / ask_counts`
のみで、仮説を保持する状態は**存在しない**。

`next_capability_turn()`は`build_hypothesis(latest_user_text)`であり、
**毎回最新発話から作り直している**。

### 8.2 §12の症状を実際に再現した

```
Turn1「釣った魚とサイズと場所を記録して、地図で見たい」
  → data=[data.number]  view=[view.list]  missing=[view.map]

Turn2「違う、よく釣れる場所ほど色を濃くしたい」
  → data=[]             view=[view.bar_chart] missing=[view.heatmap]
                ^^^^ サイズ(data.number)が消失
```

**結果が似て見えても構造が違う**という§11の指摘は正確である。
`view`だけ訂正されたのに`data`まで失われている。

### 8.3 設計

Session に仮説の状態を持たせ、**訂正は前回の仮説に対して**行う。

```
current_hypothesis      : SolutionHypothesis | None
hypothesis_history      : tuple[SolutionHypothesis, ...]
correction_history      : tuple[CorrectionRecord, ...]
acceptance_state        : PENDING | ACCEPTED | REWOUND
```

State Machine:

```
        ┌──────────────── PROBLEM ──────────────┐
        │                                        ↓
   (no hypothesis) ──→ PRESENTED ──corrections──→ REWOUND
                          │  ↑                 (Need Model再構築)
                          │  └── DATA/VIEW/TRANSFORM/EFFECT
                          │      (該当層だけ差し替え)
                          │
                          ├── UNCLEAR ──→ 1問だけ聞く(仮説は保持)
                          │
                          └── ACCEPTED ──→ BUILD
```

**保持が既定、差し替えは明示的に指示された層だけ**。これが§12への回答。

---

## 9. Capability Dependency(§29)

`TRANSFORM`と`ENCODING`を分けた結果、依存関係が表現できるようになる。

```
semantic: 「場所ごとの釣れやすさを濃淡で」
  ├ TRANSFORM/aggregate   ← group_by が要る
  │    └ DATA/choice or DATA/text  (グループ化キー)
  ├ ENCODING/color_intensity
  │    └ TRANSFORM/aggregate の出力(数値)
  └ VIEW/spatial          ← **これだけが本当に無い**
```

これにより「heatmapが無い」ではなく
**「集計と濃淡は作れる。地理描画だけが無い」**と言えるようになる。
ユーザーへ返せる情報の質が変わる。

---

## 10. Trust Model(§25)

生成物と長期検証済みCoreを同じ扱いにしない。

| Level | 意味 | 生成元 | Production利用 |
|---|---|---|---|
| `CORE` | Widget Registryに実装があり、長期運用済み | 人間 | 可 |
| `COMPOSED` | 既存Primitiveの合成のみ。新規コード無し | Forge/AI | **可**(検証通過時) |
| `CANDIDATE` | 定義は通ったが実利用実績が無い | Forge/AI | 開発時のみ |
| `EXPERIMENTAL` | 新規コードを伴う | 要人間レビュー | 不可 |

**今回Production可能なのは`CORE`と`COMPOSED`まで。**
`COMPOSED`が安全なのは、**新しい実行コードを1行も含まないから**である。
定義データがValidatorを通ることと、既存Primitiveが既に検証済みで
あることの2つで安全性が閉じる。

---

## 11. Versioning(§26)

`capability_id@major.minor`。規則:

* Primitive追加 = minor(後方互換)
* Primitiveのパラメータ意味変更 = major
* 生成済みToolは**使用時のmajorをpinする**
* Registryは複数majorを同時に保持する
* rollback = pinを戻すだけ(生成物はデータなので破棄が安全)

`COMPOSED` Capabilityがデータであることの利点がここにも出る。
コードなら rollback にビルドが要るが、定義データなら不要である。

---

## 12. Security Threat Model(§34)

| 脅威 | 該当する拡張種別 | 対策 |
|---|---|---|
| 任意コード実行 | C/E のみ | **今回は着手しない**。A/Bは実行コードを生成しない |
| Prompt injection でCapability捏造 | 全部 | AI提案はRegistry照合を通す。未知は`unknown`(§45) |
| Supply-chain | C のみ | 依存追加を許さない設計を先に選ぶ(§33) |
| Exfiltration | `EFFECT/OUTBOUND` | 既存CONFIRM Policy + 明示的許可 |
| 権限昇格 | `EFFECT/DEVICE` | **仕様生成と有効化を分離**。有効化は自動化しない |
| Capability爆発 / DoS | A/B | §7の5条件 + 定義数の上限 + 重複検索(§27) |
| Feedback poisoning | 全部 | §13 |

**A(Composition)とB(Declarative)の脅威面が小さいのは、
生成物が実行コードではなくデータであり、既存の決定的Validatorで
検査できるからである。** これが今回この2つを選ぶ理由である。

Sandboxについて(§32): A/Bには**プロセス隔離は不要**。
隔離すべき対象が無い(コードを実行しないため)。必要なのは
**スキーマ検証・参照整合性検証・Primitive allowlist**であり、
これは既存Validatorの延長で足りる。
C/Eを将来やるなら、そこで初めてfilesystem/network/subprocess/timeout
のThreat Modelが要る。**「Sandbox」と書いて済ませない**という
§32の要求に対する回答は、「今回はSandboxが要らない方式を選んだ」である。

---

## 13. User Feedbackの責任境界(§35/§36)

一人の「そう」でGlobal Capabilityを書き換えない。階層を分ける:

| 層 | 誰の「そう」で変わるか | 永続範囲 |
|---|---|---|
| Session preference | そのユーザー、その会話 | セッション内 |
| Tool specification | そのユーザー、そのTool | そのTool |
| Reusable pattern candidate | 複数ユーザー・複数Toolで反復 | 提案のみ。自動昇格しない |
| Global platform capability | **人間の判断** | Registry |

**今回実装するのは上2つまで。** 3層目以降は、複数ユーザーのデータが
存在しない現状では設計しても検証できない。

Training利用(§18)は**行わない**。User Correctionはセッション内の
理解更新にのみ使う。

---

## 14. 採用しなかった案

| 案 | 却下/延期理由 |
|---|---|
| 実行中のDart注入(Goal 1) | Flutterが動的コード実行不可。**技術的事実**として不可能 |
| Build-Time Extension(C) | 成立はしうるが、A/Bの効果を測る前に導入すると複雑性だけ増える。**A/Bで足りない範囲が実測で分かってから** |
| pub.dev依存の自動追加 | §33。供給網リスクが、得られる自由度に見合わない |
| Multi-Candidate | §47。Local実測前は導入しない(v1の判断を維持) |
| Capability自動昇格(Global) | §35。複数ユーザーデータが無い現状では検証不能 |
| User FeedbackのTraining投入 | §18。consent/privacy設計が未着手 |
| Native/Privilegedの自動有効化 | §12。仕様生成までに留める |

---

## 15. Local AI / RAG の責任境界

**Local AIの役割**: Semantic Capabilityの**提案**(§20)。
検出漏れを減らすため、キーワードで拾えない言い回し
(「地理的に可視化したい」)を意味として拾う。

**Local AIがやってはいけないこと**:
* 存在の宣言。`view.quantum_map`と言っても、Registryに無ければ`unknown`
* App Typeへの分類(§21)。Forgeは Template Selection System ではない
* 安全判定。Effectの可否はPolicyが決める

**RAGの役割**(§22): テンプレート名を返すのではなく、
**推論材料**を返す(「血圧は収縮期/拡張期の2値」「継続記録には
timestampが要る」)。今回は着手しない——Curated知識が7件しか無く、
入れる前に「その7つが実際に使われているか」の実測が先(v1 §5を維持)。

---

## 16. Migration Path

| Phase | 内容 | 可逆性 | 今回 |
|---|---|---|---|
| 1 | Stateful User Correction | 可逆 | **実装する** |
| 2 | Semantic Capability / Primitive分離 | 可逆 | **実装する** |
| 3 | Composition-first解決(A) | 可逆 | **実装する** |
| 4 | Declarative Capability定義(B、`COMPOSED`) | 可逆 | **PoCまで** |
| 5 | `TRANSFORM/aggregate`のRuntime実装 | 要Flutter変更 | **今回はしない**(§17) |
| 6 | Build-Time Extension | 不可逆要素あり | しない |
| 7 | Trust昇格の自動化 | 危険 | しない |

---

## 17. Productionへ出せる部分 / 出してはいけない部分

**出せる**:
* Stateful User Correction(既存経路に触れない。仮説が無ければ従来動作)
* Semantic Capability分解(検出の精度が上がるだけ。出力は会話文のみ)
* Composition-first解決(新Capabilityを作らず、既存で足りるかを先に見る)

**出してはいけない**:
* `COMPOSED` Capabilityの**Runtime利用**。定義は作れるが、
  `TRANSFORM/aggregate`のRuntime実装がまだ無いため、
  **今描画すると「作れたふり」になる**。PoCは定義と検証までに留める
* Effect Capabilityの自動有効化
* 生成Capabilityの自動Global昇格

---

## 18. 最初のVertical Slice(今回やること)

```
Phase 1: Stateful User Correction
  Session状態 → 訂正分類 → 該当層だけ差し替え → ACCEPT → BUILD
                                              → PROBLEM → Need再構築

Phase 2: Semantic Capability分解
  「地図で濃淡」→ aggregate + color_intensity + spatial
  → 本当に無いのは spatial だけ、と言えるようにする

Phase 3: Composition-first + Declarative定義PoC
  新Capabilityを作る前に、既存Primitiveの合成で足りるかを必ず先に見る
  足りる場合、その合成を`COMPOSED` Capability定義として登録・検証できる
```

---

## 19. 「能力を足した」と呼ぶ基準(§56)

Registryへ1行足しただけでは自己拡張とは呼ばない。次が全部成立して初めて呼ぶ:

```
Before : 要求Xが表現できない(検証可能な形で示す)
Extension: Capability追加
After  : 同じ要求Xが 表現 → 検証 → コンパイル → 描画 → 使用 できる
```

**今回のPoCは、この基準のうち「描画」「使用」に到達しない。**
`TRANSFORM/aggregate`のRuntime実装が無いためである。
したがって**今回を「Forgeが自己拡張した」とは報告しない**。
到達したのは「表現 → 検証 → コンパイル」までである。
残りに何が必要かは§16 Phase 5に明記した。

---

## 20. 成功指標(§57)

今回測れるもののみ列挙する(測っていないものを指標と呼ばない):

* `missing_detection_precision` — 50セッションで誤検出0を維持
* `unnecessary_new_capability_rate` — 合成で足りたのに新規を作った率
* `correction_context_preservation` — 訂正時に非該当層が保持された率
* `user_correction_turns` — ACCEPTまでの往復数

将来必要になるもの(今は測れない): duplicate rate, reuse count,
rollback success, security gate pass, extension latency。

---

## 21. UX(§58)

内部がどれだけ複雑でも、ユーザーには
「Capability」「Primitive」「Registry」と言わない。

```
User : 釣れた場所を地図で見たい
Forge: どこで何が釣れたか、地図に点で残す感じ？
User : 違う。よく釣れる場所ほど色を濃くしたい。
Forge: 場所ごとの釣れやすさを、濃さで見たいんだね。
       地図そのものはまだ描けないんだけど、
       場所ごとの釣果数を並べて見る形なら今すぐ作れる。それでもいい？
```

内部では
`TRANSFORM/aggregate` + `ENCODING/color_intensity` + `VIEW/spatial(missing)`
と分解しているが、**一言も出さない**。

§59の「時間がかかる場合」への回答もここに含まれる:
**勝手に代替版を押し付けず、短く確認する**。上の例の最後の一文がそれである。

---

## 22. 最大の不確実性(正直な申告)

1. **`detection_keywords`の限界**。「地理的に可視化」は今も拾えない。
   Local AI提案(§15)で補う設計にしたが、**Local Modelを一度も
   実行できていない**(TD51)ため、効果は未測定である。
2. **合成で足りるかの判定**が、現状はPrimitiveの有無だけを見ている。
   意味的に足りるか(集計だけで本当にユーザーが満足するか)は
   ユーザーに聞くしかなく、そこは会話に委ねている。
3. **`TRANSFORM/aggregate`のRuntime実装コスト**を実測していない。
   Flutter側の変更量は小さいと見積もっているが、根拠は
   `bar_chart`実装(約90行)との比較であり、実装していない。

---

## 21-bis. Semantic Architectureの接続状態(2026-08-13追記、指摘4)

**「Semantic Capability Architectureへ移行済み」ではない。**
正確な状態は次のとおりである:

| 層 | 会話での扱い |
|---|---|
| `DATA` / `VIEW` / `EFFECT` | **first-class**。`SolutionHypothesis`の層であり、`CorrectionTarget`として訂正できる |
| `TRANSFORM` / `ENCODING` | **補助的**。`semantic_capability.py`の分解・代替提示にのみ使う。訂正の対象にできない |

したがって現在は「**補助的PoCとして接続済み**」が正しい表現である。

**この差が具体的に何を意味するか**: 「集計方法が違う(合計じゃなくて
平均がいい)」「色の濃さではなく大きさで表したい」という訂正は、
**今は受け取れない**。`classify_correction()`が返せるのは
DATA/VIEW/EFFECT/PROBLEMだけであり、TRANSFORM/ENCODINGへの訂正を
表現する手段が無いからである。

**将来の設計方針(まだ実装しない)**: `CorrectionTarget`へ`TRANSFORM`と
`ENCODING`を足すのは容易だが、**訂正先のPrimitiveが1つも実装されていない
現状で足すと、「集計方法を変えたい」→「集計自体ができません」という
無意味な会話になる**。`transform.aggregate`のRuntime実装が先である。
順序を逆にしない。

---

## 22-bis. 実装後に、自分の主張を1つ修正した(2026-08-13追記)

§3.4で「集計Primitiveを1つ足すと表現の**族**が増える」と書いた。
実装後、未実装Primitiveを1つずつ実装したと仮定して成立Semantic数を
数えたところ、`transform.aggregate`・`transform.sort`・`view.calendar`・
`data.image`は**いずれも+1個**だった。この粒度では、集計だけが特別に
多くを解禁するわけではない。**主張は測定に支持されなかった。**

測定が支持したのは別の事実である:

| Semantic | 成立まで残り |
|---|---|
| `semantic.heatmap_by_place`(地図で濃淡) | 4個 |
| `semantic.map_markers`(地図に点) | 3個 |
| `semantic.ranking_by_group`(場所ごとの集計) | **1個** |

同じ困りごと(「よく釣れる場所を知りたい」)に対して、地図表現は4個先、
集計表現は1個先である。`transform.aggregate`の価値は「多くを解禁する」
ことではなく、**ユーザーの要求へ最も安く到達できる道であること**だった。

§23-1の優先順位は変わらないが、理由が変わったので記録しておく。

---

## 23. 次の最高Impact 3項目

1. **`TRANSFORM/aggregate`のRuntime実装**。これ1つで
   「場所ごと」「カテゴリごと」「月ごと」の集計表示が一斉に可能になる。
   §19の基準を初めて満たせるようになるのもここ。
2. **Local AIによるSemantic Capability提案**の実測。
   キーワード検出の限界(§22-1)を埋める唯一の手段だが、未検証。
3. **`ENCODING`層のRuntime対応**(色の濃さで値を表す)。
   `bar_chart`の描画をパラメータ化すれば、新Widgetを足さずに
   表現の族が増える——§3の主張を実証する2番目の例になる。
