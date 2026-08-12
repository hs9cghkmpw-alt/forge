# STATUS

現在のForgeが「どこまで動くか」を一枚で示す。詳細な履歴は`CHANGELOG.md`、
未解消の課題は`TECH_DEBT.md`・`KNOWN_ISSUES.md`を参照。

**最終更新**: 2026-08-12(FORGE-CONVERSATION-READY-001)

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
| Validator / Repair / Critic | 動作 | Validator最大3回・Repair最大2回 |
| Flutter Runtime | 動作 | Widget 19種、v1.8 |
| 「はい、どうぞ」UX | 動作 | `conversation_flow_screen.dart` |
| Conversation Metrics | 記録のみ | プロセス内メモリ。外部送出は未実装 |
| Voice(STT/TTS) | 未接続 | Adapterとして後から足せる構造は維持 |

## テスト

| 対象 | 件数 | 状態 |
|---|---|---|
| `forge_ai/tests` | 495 | 全green |
| `backend/tests` | 733 | 全green(skip 13) |
| `frontend`(Flutter) | 451 | 全green、`flutter analyze` 0エラー |

## 分かっている制限

* `ConversationStore`・`ConversationMetrics`はプロセス内メモリのみ
  (再起動で消える。TD41)。
* Domain分類が緩くCurated Domainへ寄ると、AI合成より品質の低い
  既製定義が使われる場合がある(TD45、例: 「血圧を記録したい」→ diary)。
* `todo`・`reading_log`はDomainCategory enumに無く、分類から到達不可能
  (TD39。ただし合成経路が同等のアプリを作るため影響は限定的)。
* Gemini無料枠のレート制限(429)に当たると生成が失敗する。
* Conversation Metricsは測れる形にしただけで、まだ運用していない。
