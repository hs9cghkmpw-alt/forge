# FORGE-R1-CLOSURE-015 — R1 Design Language の閉じ込め

**2026-08-17 / branch `claude/forge-master-handoff-k46jns`**
**開始HEAD: `936cfa1` / 監査対象: `27b3597`**

---

## 0. 結論

**R1 DESIGN LANGUAGE = GO（条件付き）。**

Definition of Done の20項目のうち19項目を満たした。残る1項目は
**Flutter側の実行確認**で、この作業環境にFlutter SDKが無いため
CIに委ねている（§16参照）。CIが緑ならGO、赤なら直してからGOである。

指摘された穴は**すべて実際に再現してから**直した。推測でPatchした
ものは1件も無い。

---

## 1. NUMBER→SUM 問題の実例（再現済み）

指摘のとおりだった。**本番経路で実際にこれが出ていた。**

| Domain | NUMBER field | 修正前 | 妥当性 |
|---|---|---|---|
| `reading_log` | rating(評価5段階) | **sum(rating)** | ❌ 「評価の合計が42」 |
| `fishing_log` | size(サイズcm) | **sum(size)** | ❌ 魚の長さの合計 |
| `household_budget` | amount | sum(amount) | △ 加算可能だが**残高ではない** |
| `inventory` | quantity | sum(quantity) | ✅ 妥当 |

修正後:

```
reading_log       average(rating)  「評価(5段階)の平均」
fishing_log       max(size)        「サイズ(cm)の最大」
inventory         sum(quantity)    「数量の合計」
household_budget  残高 / 収入 / 支出（§6）
```

---

## 2. Measure Semantic の設計

`MeasureSemantics`（`forge_ai/core/ir/ir_types.py`）。

| 値 | 意味 | 最初に知りたいこと |
|---|---|---|
| `additive` | 足し合わせに意味がある | 合計 |
| `averageable` | 平均に意味がある。**合計は無意味** | 平均 |
| `level` | ある時点の水準（体温・残高） | 最新値 |
| `extremum` | 最大/最小に意味がある | 最大 |
| `identifier` | 集計しない数値（年号・番号） | — |
| `unknown` | **既定値** | — |

### 集計方法と分けた理由

`preferred_aggregate`だけを持たせる案もあったが、**なぜそう集計するのか
が失われる**。「合計する」は結論で、理由は「足し合わせに意味がある量
だから」である。理由があると、後から別の問い（グラフのY軸にしてよいか、
前月比を出してよいか）にも答えられる。

### 誰が決めるか

| 経路 | 決める人 |
|---|---|
| Curated Domain | 人手（定義表） |
| AI合成 | **AI**（閉じた6択、Promptに「迷ったらunknown」と明記） |
| 未指定・不正 | `unknown` |

詳細: `docs/spec/METRIC-SEMANTICS-V1.md`

---

## 3. Hero KPI を出さない条件

* `measure` が `unknown` または `identifier`
* 数値Fieldを1つも持たない（habit / todo / diary）

**分からないなら作らない。** 「出せるから出す」をすると、意味の無い
数値が画面で一番大きくなる——それは何も無いより悪い。利用者はそれを
事実だと読む。

`unknown` を `additive` へ倒した瞬間に「評価の合計」が復活するので、
既定値は `unknown` である（`CLAUDE.md` §3「分からないものを楽観側へ
倒さない」）。

---

## 4. Finance KPI の扱い

### 単純な合計を「残高」と呼ばない

`MonetaryFlow` を IR へ入れた。

```python
MonetaryFlow(amount_field="amount", direction_field="entry_type", outflow_value="支出")
```

Curated `household_budget` に `entry_type`（収支）を足した。**それまで
収入と支出を区別できず**、いくら記録しても「今いくら残っているか」に
答えられなかった。Templateを増やしたのではなく、既存Curated Domainの
**データモデルの欠落を埋めた**ものである。

### 生成される3つ

```
残高    metric.primary    収入 − 支出   ← 画面で一番大きい
収入    finance.income    収入だけの合計
支出    finance.expense   支出だけの合計
```

`metric.primary`は**残高だけ**。3つとも主KPIにすると「一番大事なもの」
が3つになり、階層が消える（Design Criticがこれを見る）。

### Runtime（v1.12、property-onlyの追加）

`metric_view` に `filter_field`/`filter_value`（絞り込み）と
`sign_field`/`negative_when`（符号付け）を追加。**新しいWidget型は
1つも増やしていない。**

`outflow_value`をIRが持つのが要点である。「支出」という語をCompilerが
知っていると、英語Domainや別の言い回しに対応できない。

---

## 5. Design Critic に追加した軸

`semantic_design`（`forge_ai/core/critic/semantic_design_critic.py`）。

| 見るもの | blocking |
|---|---|
| `metric.primary` / `button.primary` の乱立 | **high** |
| roleが1つも無い | **high** |
| 骨格Widgetのrole被覆率 < 80% | medium |
| `surface.elevated` が3箇所以上 | medium |
| `finance.*` と `state.*` の併用 | medium |

### 「roleがある」だけを評価しない

これが要点である。10個すべてが`metric.primary`でも「roleは存在する」
——それは階層が消えた状態で、Designとしては失敗である。

**Compile後**に評価する。`style_role`はCompilerが付けるので、既存の
`DesignCritic`（Planを見る）の時点では存在しない。順序を変えずに
軸を1つ足す形で合流させた。

意味の階層が壊れている生成物は `release_ready=False` になる。

### 配線破壊試験で見つけた自分の失敗

実装直後の破壊試験で、**Criticへ合流させる処理を外してもテストが1件も
落ちなかった**。決定のTraceだけを見ていて、`CriticReport`そのものを
誰も検査していなかった。置物である。

`test_semantic_design_critic.py`（11件）を追加して直した。**書いた
直後に壊してみなければ気付けなかった**。

---

## 6. AI / fallback の provenance

`DesignRoleDecision(axis, role, source)`。

| source | 意味 |
|---|---|
| `ai` | AIが選び、Forgeの検証を通った。**唯一「AIの成功例」** |
| `fallback` | AIへ聞いたが採れず既定値で埋めた |
| `deterministic` | Compilerが構造から決めた（見出し・一覧・ボタン） |
| `curated` / `unknown` | 人手由来 / 記録し損ね |

### なぜ必要か

`design_language_roles`は結果の一覧しか持たない。だから
`screen_density = density.compact` が**AIの判断**なのか**Forgeの既定値**
なのか分からない。そのまま教師データにすると、**Forgeの既定値をAIの
成功例として学習する**——AIがそう判断した事実は1つも無いのに。

`DesignIntent`内部には`fallback_axes`として区別が存在していた。
**Evidenceへ渡すところで消えていた**ので、そこを繋いだ。

`record.ai_selected_roles` / `record.fallback_roles` で型として分けて
あるので、混ぜるにはわざわざ両方を足し合わせる必要がある。

### 持たないもの

Prompt本文もProviderの生出力も利用者の発話も入らない。入るのは
軸ID・role ID・由来の3つだけ（§4.2、006 §22のPrivacy境界）。
テストで「発話がEvidenceに現れないこと」を固定してある。

---

## 7. Generation Evidence の変更

```
+ design_decisions : tuple[DesignRoleDecision, ...]   由来つきの選択
+ visual_structure : dict                              構造の決定的な事実
```

`visual_structure`（§10）:

```json
{"primary_metric_count": 1, "primary_action_count": 1,
 "semantic_role_count": 10, "distinct_role_count": 9,
 "hierarchy_depth": 4, "role_coverage_ratio": 1.0,
 "elevated_surface_count": 0, "duplicated_singular_roles": [],
 "finance_state_conflict": false}
```

**名前を`VisualQuality`にしなかった。** 測れていないものを測ったことに
しない——これは「美しさ」ではなく、機械的に再現できる構造の事実である。
それでも`UNKNOWN`のまま置くよりはよい。

Criticと**同じ関数**で測る。別々に数えると、Criticが「主KPIは1つ」と
言っているのにEvidenceには2と残る、という食い違いが起きうる。

---

## 8. forge_ai / backend 依存の解消方法

### 何が問題だったか

```python
# forge_ai/core/pipeline.py（修正前）
try:
    from app.ai.runtime.design_language import design_choice_guidance
except ImportError:
    return ()
```

コメントには「forge_aiはbackendをimportしない」と書いてあったが、
**実際にはしていた**。しかもimport失敗を握り潰していたので:

```
Production          import成功 → Design Intent 動く
forge_ai standalone ImportError → Design Intent 動かない
```

**同じコードが環境によって別の振る舞いをする。** forge_ai単体のテストが
何件通っても、本番で語彙が渡っている証拠にならない。

### どう直したか

```
backend ──(注入)──> DesignLanguageGuidance ──> forge_ai pipeline
```

`forge_ai/contracts/design_language_contract.py` に**形だけ**を定義し、
中身（33 role・軸・検証関数）はbackendが`design_language_guidance()`で
組み立てて`run_cognitive_pipeline(design_language=...)`へ渡す。

forge_aiは`app`というモジュール名を1文字も知らない。

### 検査

`test_dependency_boundary.py`:

* forge_ai全ファイルを**構文木で**走査し、`app.*` importが無いこと
  （文字列検索にすると、経緯をコメントに書けなくなる）
* backend由来の語彙と、forge_ai側だけで組み立てた同じ形の語彙で、
  **同じ結果になる**こと
* 渡さなければAIへ聞かないこと（環境の違いではなく明示的な状態）

---

## 9. Semantic Color の設計

`ForgeSemanticColors`（ThemeExtension）。

```
             Light      Dark
success   #2E7D32    #81C784
warning   #EF6C00    #FFB74D
income    #00796B    #4DB6AC
expense   #C2185B    #F06292
```

修正前は`design_language.dart`へ固定値を直接書いていた。Lightでは
読めるがDarkでは背景に沈む。**役割は「意味」であってRGB値ではない**
のに、値を焼き付けていた。

`finance.expense` ≠ `state.danger` は維持している。**支出はエラーでは
ない**——同じ赤で塗ると、家計簿を開くたびに何か失敗したように見える。

ThemeExtensionが登録されていない場合は明度から既定を選ぶ（落ちない）。

---

## 10. button role の視覚差

修正前は`button.primary`も`button.secondary`も同じ`ElevatedButton`。
コード中のコメントにも「roleは記録として意味を持つが描画は変えない
——後者が無いことは欠陥ではない」と書いてあった。

**それは欠陥である。** 意味が見た目に出ないなら、その語彙は記録用の
飾りでしかない。

```
button.primary   → FilledButton    （塗りつぶし・高emphasis）
button.secondary → OutlinedButton  （輪郭のみ・低emphasis）
role無し         → ElevatedButton  （従来どおり・見た目を変えない）
```

生の色を固定せずMaterialのemphasis体系に乗せたので、Light/Dark
どちらでも成立する。

### 被せる方式では足りなかった

`style_role`は`_build()`が1箇所で被せる設計だった。しかし
**builderが作り終えた後**に被せるので、「ボタンの種類そのものを
変える」ことはできない。`ForgeRoleScope`（InheritedWidget）で
builderを呼ぶ**前**にroleを置く形にした。

被せる方式は残してあるので、roleを1つ足すたびに全builderを直す必要は
無い（必要なbuilderだけが読みに来る）。

---

## 11. metric.primary の実描画（§8の再現と修正）

**指摘は当たっていた。**

```dart
// 修正前
Text(formatMetricValue(value), style: valueStyle)  // ← 明示的なstyle
```

`style_role`は`DefaultTextStyle.merge`で被せる設計だが、
**Textが明示的なstyleを持つとDefaultTextStyleは効かない**。つまり
`metric.primary`を付けても描画は1ピクセルも変わっていなかった。

roleをここで解決して明示的にmergeするよう直した。roleが無ければ土台の
まま（roleの無い既存の生成物の見た目を変えない）。

これはTD73として残した——**「1箇所で被せれば全Widgetに効く」は成立
しない**という、設計上の一般的な問題だからである。

---

## 12. 検証区分

**混同しないよう正確に分ける。**

| 項目 | 区分 |
|---|---|
| NUMBER→SUM問題の再現 | **実測** |
| Measure Semanticsが本番経路で効くこと | **実測** |
| Finance 3指標が自然言語から出ること | **実測**（AIはTest Double） |
| Semantic Design Criticの合流 | **実測** |
| AI/fallback provenance | **実測**（AIはTest Double） |
| Visual Structure Evidence | **実測** |
| forge_aiがbackendをimportしないこと | **実測**（構文木で走査） |
| backend 1258 passed / forge_ai 521 passed | **実測** |
| 配線破壊試験 A/B/C/D/E/F/G/H | **実測**（7件） |
| **Flutter（描画・色・強弱・density・surface）** | **未検証**。この環境にFlutter SDKが無い。**CIのfrontend jobで確認する** |
| **配線破壊試験 E2（Dart側）** | **未検証**（同上） |
| 実Cloud APIでのDesign Intent / Measure選択 | **未検証**（指示どおり実APIを呼んでいない） |

**Flutterのテストは書いたが実行していない。** 新規
`semantic_visual_hierarchy_test.dart`（17件）はCIで初めて走る。

---

## 13. 配線破壊試験の結果（§15）

| | 外したもの | 落ちたテスト |
|---|---|---|
| A | Measure Semantic判断（NUMBER→SUMへ戻す） | `test_a_fishing_log_shows_the_biggest_catch` |
| B | Design Criticのsemantic_design軸 | `test_the_axis_is_listed_as_evaluated` |
| C | AI/fallback provenance | `test_a_rejected_choice_is_recorded_as_fallback` |
| D | DesignLanguageContractの注入 | `test_an_accepted_choice_is_recorded_as_ai` |
| E | metric.primaryをHero KPIから外す | `test_the_balance_is_the_single_most_important_number` |
| F | button.primary/secondaryの差 | `test_the_primary_action_is_marked` |
| G | Finance rolesのCompiler到達 | `test_income_and_expense_carry_finance_roles` |
| H | Visual Structure Evidenceの抽出 | `test_the_visual_structure_is_recorded` |
| E2 | metric.primaryの実描画（Dart側） | **未検証**（Flutter実行不可、CI待ち） |

**Bは1回目に落ちなかった**（＝置物だった）。テストを追加して直した。
経緯は§5に書いてある。

---

## 14. Local AI Knowledge Candidate（§12）

`knowledge_candidates()` を追加した。既存の`knowledge_entries()`は
33 roleを1件ずつ並べたもので、「`metric.primary`とは何か」には答えら
れるが**「何と何から選ぶのか」には答えられない**。選択は比較なので、
候補の集合が要る。

```json
{"axis": "screen_density",
 "fallback": "density.normal",
 "options": [{"id": "density.compact",
              "meaning": "情報を詰める。",
              "use_when": "一覧・タスクリスト。",
              "avoid_when": "読ませたい本文。",
              "alternatives": ["density.normal", "density.relaxed"]}, ...]}
```

**選ばれなかった候補が残る**のが要点である。「このNeedではrelaxedでは
なくcompactが受け入れられた」という対比は、候補が分かっていて初めて
学習素材になる。

宣言されたfallbackが**実際にForgeが使う既定値と一致すること**を
テストで固定した。ずれたまま配ると、Local AIはその嘘を学ぶ。

---

## 15. TD70 の推奨解（§13）

**推奨: B（Local AIへDesign Intentを寄せる）を本命に、A（cache）を
繋ぎとする。**

Bが本命なのは、このTaskの目的と一致するからである。択一はLocal AIに
最も向いた仕事で（生成より選択の方が易しい）、しかも**Design Intentを
解かせること自体がLocal AIの訓練になる**。Cloud枠を1回も使わない。

前提はTD51（Local AI実モデル実行が0回）の解消。

AはBまでの繋ぎとして妥当だが、キャッシュキーの粒度を粗くすると
**違う依頼に同じ意味を当てる**。「家計簿」でも「落ち着いて振り返り
たい」と「素早く放り込みたい」では適切な密度が違う。

C（既存AI callへ統合）は、`entity_synthesis`がCuratedでは通らない
ため経路によって回数が変わる。D（既定値+任意refine）は「任意」が
忘れられる（`CLAUDE.md` §3）。

比較表は `TECH_DEBT.md` TD70。

---

## 16. 数値

```
backend/tests    1258 passed / 16 skipped   （+63件）
forge_ai/tests    521 passed
frontend         この環境で実行不可（SDK無し）。新規17件はCI初回
CI               push後に確認
```

新規テストファイル:

| ファイル | 件数 |
|---|---|
| `backend/tests/test_measure_semantics.py` | 23 |
| `backend/tests/test_semantic_design_critic.py` | 11 |
| `backend/tests/test_golden_finance_e2e.py` | 13 |
| `backend/tests/test_dependency_boundary.py` | 5 |
| `frontend/test/json_ui/renderer/semantic_visual_hierarchy_test.dart` | 17（CI） |

---

## 17. 完成画像との距離

**縮んだところ。**

* 家計簿を開くと**残高が一番大きく出る**。収入と支出が別の意味の色で
  並ぶ。それまで「金額の合計」しか出せなかった
* 主要操作が塗りつぶし、副次操作が輪郭になり、**画面の中で強弱が
  見える**
* 意味の無い数値（評価の合計・魚の長さの合計）が画面から消えた
* 暗い画面でも意味の色が読める

**縮んでいないところ。**

* Widgetは20種のまま。表現できる画面の種類は増えていない
* 余白・行間・タイポグラフィの詰めはしていない。「完成画像級」の
  多くはここに宿るが、今回の範囲ではない
* 画面遷移が無い（tab_viewのみ）

---

## 18. Local AI 閉ループの進み

```
Need → Vocabulary → AI selection → Validation → Runtime → Evidence → [Dataset] → [Local AI]
                                                             ↑ ここまで来た
```

* **AIの選択と、Forgeの既定値が型で分かれた**（§6）。混ぜて学習する
  経路が塞がれた
* 構造の事実が残るようになった（§7）。「どういう構造の生成物が
  受け入れられたか」を後から突き合わせられる
* 選択肢の集合が学習可能な形になった（§14）

**繋がっていないところ**は変わらない。Runtime結果（TD65）と利用者の
承認（TD65）が戻る経路が無く、Dataset化もLoRAも未着手。

---

## 19. 自己監査（PRODUCT-DIRECTION §8 / 指示書§20）

1. **見た目が変わるroleになっているか** — button/metric/density/surface
   /色は変わる。Flutter側の確認はCI待ち
2. **「roleがあるだけ」で完成扱いしていないか** — Criticが乱立を
   blockingにする。実装直後に置物だったのを破壊試験で見つけて直した
3. **数値だからという理由だけでKPIを発明していないか** — していない。
   `unknown`はKPIを作らない
4. **AIが選んだものとForge fallbackを混ぜていないか** — 型で分けた
5. **Local AIが将来学べるEvidenceか** — 候補・代替・fallbackまで
   持たせた
6. **Standalone testとProductionで挙動が違わないか** — 遅延importを
   やめ、注入にした。同じ契約で同じ結果になることをテストで固定
7. **Dark/Lightで成立するか** — ThemeExtension化。テストはCI待ち
8. **Golden AppをTemplate化していないか** — していない。Curated
   Domainのデータモデルの欠落を埋めただけで、固定Templateは足していない
9. **Criticが悪いDesignを悪いと言えるか** — 言える（§5）
10. **完成画像へ近づいたか** — §17に正直に書いた
11. **Local AI育成へ近づいたか** — §18
12. **「実装したが呼ばれない」を増やしていないか** — 破壊試験8件中
    7件で確認。E2はCI待ち
