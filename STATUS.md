# STATUS

現在のForgeが「どこまで動くか」を一枚で示す。詳細な履歴は`CHANGELOG.md`、
未解消の課題は`TECH_DEBT.md`・`KNOWN_ISSUES.md`を参照。

**最終更新**: 2026-08-14(FORGE-AI-FOUNDATION-010)

> このファイルはFORGE-CONVERSATION-READY-001指示書15章の要請で新設した。
> それ以前は同等の役割を`KNOWN_ISSUES.md`と各`*-report.md`が分担しており、
> 「今どこまで動くか」を一箇所で見る文書が無かった。

## 通っている一本道

```
困りごとを話す
  → 必要最小限だけ質問(Question Policy)
  → 危ないことは会話の中で確認(CONFIRM)
  → 自然にToolが現れる(「はい、どうぞ」)
  → 会話で育てる(UPDATE)
```

この経路は端から端まで実装・テスト済みである。

## レイヤー別の状態

| レイヤー | 状態 | 実体 |
|---|---|---|
| Conversation判断 | 動作 | `conversation_engine.py` + `conversation_policy.py` |
| Readiness / Question / Confirm Policy | 動作 | `conversation_policy.py`(5値のReadiness) |
| Build失敗時のフォールバック | 動作 | 理解段階の失敗のみASKへ戻す |
| Cognitive Pipeline | 動作 | `forge_ai/core/orchestration/pipeline_orchestrator.py`(13段階) |
| Entity合成(任意Domain対応) | 動作 | `forge_ai/core/ir/entity_synthesizer.py` |
| Forge Language生成 | 動作 | Curated 5 Domain + 合成経路 |
| Solution Shape選択 | 動作 | CHECKLIST / RECORD_CRUD の2形 |
| Validator / Repair / Critic | 動作 | Validator最大3回・Repair最大2回 |
| Flutter Runtime | 動作 | Widget 19種、v1.9(集計付きbar_chart) |
| 「はい、どうぞ」UX | 動作 | `conversation_flow_screen.dart` |
| Conversation Metrics | 記録のみ | プロセス内メモリ。外部送出は未実装 |
| AI Router | 動作 | Quota/健全性/Circuit Breaker。**全AI呼び出しが経由**(迂回を回帰で固定) |
| Model Gateway | **削除** | `AIRouter`と責務が重複し本番未使用だった(TD59)。同じ層を2つ残さない |
| Provider Registry | 動作 | Providerの唯一の宣言。名前・鍵の変数名・実装状況・protocol |
| Provider Auto Discovery | 動作 | 環境変数が揃ったProviderだけが候補になる |
| Model fallback(Provider内) | 動作 | 一時的失敗・Model廃止・PER_MODEL枠切れのとき、同じProviderの別Modelへ進む。Provider Identityは増やさない(011 §1) |
| **Gemini無料枠** | **観測1 Modelで20** | 実測は429本文の`quotaValue=20`・`quotaId=PerProjectPerModel`のみ。合計値と枠の単位(Project/鍵)は**未検証**(TD66)。検証作業だけで上限到達したので実運用には足りない |
| Local Provider | 実装済/未実測 | OpenAI互換。実モデル未実行(環境制約、TD51) |
| 2つ目のCloud枠(`cloud`) | 実装済/未実測 | OpenAI互換なら環境変数3つで載る。**実APIでは未検証** |
| Provider Benchmark | 動作 | Impact分類16ケース。harness実行確認済み |
| Benchmark → Routing接続 | **配線済/データ待ち** | 実測(REAL)が2 Provider揃えば品質順になる。今は記録が無く宣言順 |
| Local AI 学習基盤 | **記録開始** | R0で`/converse`・`/generate`・`/update`から実際に記録。実Geminiで確認済み。学習・永続化は未着手 |
| └ 生成物のEvidence | 動作 | 013で`GenerationRecord`を追加。**AIを呼ばないCurated生成も**`source=curated`として残る(TD65解決) |
| └ Experience記録 | 動作 | 記録地点は`AIRouter.generate()`の1箇所。Validatorの合否・利用者の承認/訂正を後から書き足す |
| └ 学習(Dataset/LoRA) | 未着手 | 記録はプロセス内メモリのみ(TD41)。`ABANDONED`は未検出(TD64) |
| Scripted Conversation Set | 動作 | 50セッション。平均質問1.20/繰り返し0/未決着0 |
| Capability検出 / 仮説提示 | 動作 | `capability.py`。作れないものを名指しし、作れる形を出す |
| Stateful User Correction | 動作 | 前回の仮説を保持し、訂正された層だけ差し替える |
| Semantic Capability分解 | **PoC / 部分統合** | 分解・代替提示に使う。TRANSFORM/ENCODINGは訂正対象に**未統合** |
| `transform.aggregate` | 動作 | グループごとの集計。**Compiler未接続**(会話からは到達しない) |
| Declarative Capability定義 | 検証まで | 信頼度(`TrustLevel`)と実行可否(`ExecutionReadiness`)を別軸で持つ。**本番利用は不可** |
| Self-Extension(能力獲得) | **目標として継続** | 5段階(表現→検証→コンパイル→描画→利用)のうち**2段階目まで**。定義は`FORGE-SELF-EXTENSION-ARCH-REVIEW-v2.md` §2 |
| └ 実行中のDartコード注入 | **不採用** | Flutterが動的コード実行不可。これは技術的事実 |
| └ 宣言的Capability定義 | 検証まで | 既存Primitiveの合成をデータとして追加。Runtime利用は不可 |
| 模擬出力の明示 | 動作 | `simulated`フィールド + Flutter側のバナー/バッジ |
| Voice(STT/TTS) | 未接続 | Adapterとして後から足せる構造は維持 |
| CI(GitHub Actions) | 動作 | `.github/workflows/ci.yml`。backend(3.11/3.12)・**backend smoke(起動+CORS)**・Flutter(analyze/test/**build web**)。実APIは呼ばない |

## テスト

| 対象 | 件数 | 状態 |
|---|---|---|
| `forge_ai/tests` | 521 | 全green |
| `backend/tests` | 1118 | 全green(skip 16。うち3件はLive API Test、既定SKIP) |
| `frontend`(Flutter) | 476 | 全green |
| `flutter analyze` | 0件 | 2026-08-13にwarning/info含めて0へ(以前は77件) |

> 2026-08-13訂正: このセクションは以前「Flutter 451 / analyze 0エラー」と
> 書いていた。件数が古かったのに加えて、**「0エラー」は正確ではあっても
> 誤解を招く書き方**だった——errorは0だが、warning/infoが77件残っていた
> (CEO実機のFlutter 3.44.7でも77件と報告された)。同じSDK(3.44.9)を
> 用意して実際に走らせ、77件すべてを解消した上でこの行を書き直している。

## 分かっている制限

* `ConversationStore`・`ConversationMetrics`はプロセス内メモリのみ
  (再起動で消える。TD41)。
* ~~Domain分類が緩くCurated Domainへ寄る問題(TD45)~~ → **解消**(TD49)。
* **Local Modelを実モデルで一度も動かせていない**(TD51)。サンドボックスは
  `huggingface.co`がネットワークポリシーで拒否・GPU無しのため、モデル重みを
  取得できない。手順は`docs/development/LOCAL_MODEL_SETUP.md`。
* Declarative Capability定義は**検証までで、Runtime利用は不可**。
  `transform.aggregate`がRuntime未実装のため、今描くと「作れたふり」に
  なる(`FORGE-SELF-EXTENSION-ARCH-REVIEW-v2.md` §17・§19)。
* 「地図で濃淡」に必要な4つのPrimitiveのうち、**`transform.aggregate`だけが
  実装済み**である(2026-08-13、Phase 4)。残る3つ(`data.geo` /
  `encoding.color_intensity` / `view.spatial`)は未実装。
  ただし性質が違う: **新しい描画の実装が要るのは`view.spatial`だけ**で、
  残る2つは表示パラメータ・データ型であり、既存の描画(`bar_chart`等)の
  上で成立する。「何が足りないかを種類ごとに言える」とは、この違いを
  言えるという意味である。

  > 2026-08-14訂正(FORGE-AI-FOUNDATION-011 §6): この行は以前
  > 「4つ**いずれも**未実装」と書いていたが、同じファイルの上の表では
  > `transform.aggregate`を「動作」としており、**矛盾していた**。
  > Phase 4で実装した際に、こちらの行を直し忘れていた。実コードを
  > 確認して訂正した(`semantic_capability.py`で`implemented=True`、
  > Runtimeは`frontend/lib/json_ui/runtime/forge_aggregate.dart`、
  > Validatorはv1.9対応済み)。
* `transform.aggregate`の「実装済み」は**Runtimeとしての意味**である。
  Cognitive Pipeline側のCompilerは`group_by`/`aggregate`を1度も出力しない
  (`grep -rn "group_by" forge_ai/` が0件)。したがって**会話からは
  到達しない**。手書きのForge Documentを`/update`等で渡せば描画される。
* 同じ困りごと(「よく釣れる場所を知りたい」)に対して、地図表現は
  Primitiveが3個先。集計表現はPrimitiveとしては**0個先**だが、
  会話から到達させるにはCompiler接続が要る。
* 「作れない」は3種類に分けて扱う: `EXACT`(作れる)/ `FALLBACK`(代替なら
  作れる)/ `BLOCKED`(有用な代替も無い)。ただし判定は分解表の粒度に
  依存しており、`view.calendar`のようにCapability側には代替(一覧)が
  あるのにSemantic側では`BLOCKED`になる例が残っている(既知の不一致)。
* AI Routerは**Quota残量の実測をしていない**。枠切れは「429を受けたら
  学習する」という事後的な方法であり、事前の残量把握はしていない。
* **実APIで動作を確認できているのはGeminiだけである。** `local`は環境制約で
  実モデル未実行(TD51)、`cloud`枠はAdapterを実装したが実APIでは未検証
  (TD62)。したがって「Multi-Cloud Routingが動く」とは書けない——
  Test Doubleで A→B のfallbackが成立することは確認済みだが、それは
  **Routerの契約**の確認であって、複数Cloudの実地確認ではない。
* Benchmarkによる品質Routingは**配線済みだがデータが無い**。実測を
  入れるまでは宣言順で動く。Test Doubleで測った数字は構造的に弾かれる。
  (動かないProviderを候補に並べない方針、§36)。
* **内容によるPrivacy判定をしていない**(TD60)。健康情報等もCloudへ送られる。
* 共有・通知などのEffect Capabilityは**確認は取るが、実装が無い**。
  確認文を「できないこと」に合わせて書き換えるのは、指示書001 §4で
  定めたCONFIRMの意味を変えるため、今回のVertical Sliceの範囲外とした
  (`capability.py`の`has_buildable_gap()`参照)。
* 地図・カレンダー・写真・折れ線は**検出できるが作れない**。会話では
  作れないことを名指しし、作れる形を提示する(黙って別物を作らない)。
* Gemini依存が`schemas/ai.py`の`Literal["mock","gemini"]`(3箇所)に残る
  (HTTP APIの許可リスト。Local公開はBenchmark後の判断)。
* `todo`・`reading_log`はDomainCategory enumに無く、分類から到達不可能
  (TD39。ただし合成経路が同等のアプリを作るため影響は限定的)。
* Gemini無料枠のレート制限(429)に当たったとき何が起きるかは、
  **他に使えるProviderがあるかどうかで変わる**(2026-08-14、011 §6で
  Router Architectureに合わせて書き直した)。

  * **他に設定済みのProviderがある場合** — AIRouterが429を
    `RATE_LIMITED`(または枠切れなら`QUOTA_EXHAUSTED`)として分類し、
    次の候補へfallbackする。Geminiは`Retry-After`が示す時間まで、
    分からなければ既定時間まで候補から外れる。利用者から見ると
    生成は成功する。
  * **他に設定済みのProviderが無い場合** — 生成は失敗する。
    レスポンスは`provider_error`(sub_reason=`rate_limited`)で、
    「しばらく待ってからもう一度」という日本語の案内を返す。
    **Mockへ黙って倒れることはしない**(§9)。

  なお、この分類とfallbackはTest Doubleで検証済みだが、**実際の429を
  受けた実機確認はしていない**(§38「429を出すために無料枠を大量消費
  しない」)。
* Conversation Metricsは測れる形にしただけで、まだ運用していない。
* 解の形が`CHECKLIST`・`RECORD_CRUD`の2つしかない。カウンタ形は
  Forge Languageに動的な加算Actionが無いため作れない(TD48)。
* 実機Geminiでの`CHECKLIST`到達は未確認(無料枠上限のため)。
