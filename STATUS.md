# STATUS

現在のForgeが「どこまで動くか」を一枚で示す。詳細な履歴は`CHANGELOG.md`、
未解消の課題は`TECH_DEBT.md`・`KNOWN_ISSUES.md`を参照。

**最終更新**: 2026-08-13(FORGE-HANDOFF-LOCAL-AI-UX-004 / FORGE-ARCHITECTURE-REVIEW-AND-IMPLEMENT-005)

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
| Flutter Runtime | 動作 | Widget 19種、v1.8 |
| 「はい、どうぞ」UX | 動作 | `conversation_flow_screen.dart` |
| Conversation Metrics | 記録のみ | プロセス内メモリ。外部送出は未実装 |
| Model Gateway | 動作 | Task単位のRouting・計測・fallback |
| Local Provider | 実装済/未実測 | OpenAI互換。実モデル未実行(環境制約) |
| Provider Benchmark | 動作 | Impact分類16ケース。harness実行確認済み |
| Scripted Conversation Set | 動作 | 50セッション。平均質問1.20/繰り返し0/未決着0 |
| Capability検出 / 仮説提示 | 動作 | `capability.py`。作れないものを名指しし、作れる形を出す |
| Stateful User Correction | 動作 | 前回の仮説を保持し、訂正された層だけ差し替える |
| Semantic Capability分解 | 動作 | `semantic_capability.py`。不足を種類ごとに特定する |
| Declarative Capability定義 | 検証まで | `capability_definition.py`。**Runtime利用は不可**(§17) |
| Self-Extension(能力獲得) | **目標として継続** | 定義は`FORGE-SELF-EXTENSION-ARCH-REVIEW-v2.md` §2。到達は「表現→検証」まで |
| └ 実行中のDartコード注入 | **不採用** | Flutterが動的コード実行不可。これは技術的事実 |
| └ 宣言的Capability定義 | 検証まで | 既存Primitiveの合成をデータとして追加。Runtime利用は不可 |
| 模擬出力の明示 | 動作 | `simulated`フィールド + Flutter側のバナー/バッジ |
| Voice(STT/TTS) | 未接続 | Adapterとして後から足せる構造は維持 |

## テスト

| 対象 | 件数 | 状態 |
|---|---|---|
| `forge_ai/tests` | 521 | 全green |
| `backend/tests` | 852 | 全green(skip 13) |
| `frontend`(Flutter) | 455 | 全green |
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
* 「地図で濃淡」に必要な4つのPrimitive(`data.geo` / `transform.aggregate` /
  `encoding.color_intensity` / `view.spatial`)は**いずれも未実装**である。
  ただし性質が違う: **新しい描画の実装が要るのは`view.spatial`だけ**で、
  残る3つはデータ変換・表示パラメータ・データ型であり、既存の描画
  (`bar_chart`等)の上で成立する。「何が足りないかを種類ごとに言える」
  とは、この違いを言えるという意味である。
* 同じ困りごと(「よく釣れる場所を知りたい」)に対して、地図表現は
  4個先、集計表現は**1個先**(`transform.aggregate`のみ)。
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
* Gemini無料枠のレート制限(429)に当たると生成が失敗する。
* Conversation Metricsは測れる形にしただけで、まだ運用していない。
* 解の形が`CHECKLIST`・`RECORD_CRUD`の2つしかない。カウンタ形は
  Forge Languageに動的な加算Actionが無いため作れない(TD48)。
* 実機Geminiでの`CHECKLIST`到達は未確認(無料枠上限のため)。
