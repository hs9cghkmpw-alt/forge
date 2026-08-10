# backend/app/ai/runtime/ — ステータス

**Status: EXPERIMENTAL — NOT CONNECTED — NOT USED IN PRODUCTION PATH**
**マイルストーン: M005(Backend AI Integration)。旧称
「FORGE-MILESTONE-004: Native AI Phase-1」は、`docs/spec/
FORGE_AI_ARCHITECTURE_V1.md`(Architecture Freeze、2026-07-14確定)により
M005として正式に読み替える。**

このディレクトリのコードは、CEOがChrome実機で確認した生成フロー
(`MockAppGenerationRepository` → Mock Generator → Forge Language JSON →
Dart Runtime)からは**一度も呼び出されていない**。

| 項目 | 状態 |
|---|---|
| 実際のAPIエンドポイント(`/api/v1/ai/generate`等)からの呼び出し | ❌ 無し |
| 実LLM Provider(OpenAI/Claude/Gemini)への接続 | ❌ 無し(Stub、`NotImplementedError`) |
| Forge Native AI(`forge_ai/`)との接続 | ❌ 無し(型は一部再利用しているが、実行時の呼び出しは無い) |
| CEOがこれまで実機確認した生成フローとの関係 | **無関係**。実機確認は全てMock Mode |
| Unit Testでの実行 | ✅ あり(Protocol/Stub・ルーティングロジック・オーケストレーション
  ロジックの検証。AI推論そのものは検証していない) |

## このディレクトリに何があるか

`docs/spec/AI_RUNTIME.md`・`docs/spec/PROMPT_PIPELINE.md`・
`docs/spec/NATIVE_AI_ROADMAP.md`に詳細がある。要約すると、将来
Forge Native AIを実装する際の「土台」(Protocol定義・オーケストレーション
の骨格)であり、**現時点では実行しても何も生成しない**
(`AIPlanner`等のStubを呼ぶと`NotImplementedError`が送出される)。

## いつ"接続済み"になるか

このREADME、および上表の内容は、実際に本番の生成フローから
このディレクトリのコードが呼ばれるようになった時点で、CEO承認のもとで
更新する。それまでは「Experimental」のステータスを維持する。
