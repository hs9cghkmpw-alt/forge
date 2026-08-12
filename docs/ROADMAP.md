# Roadmap

## Phase 0 — 開発基盤（現在地）
- [x] フォルダ構成設計（Clean Architecture / Feature First / レイヤードアーキテクチャ）
- [x] ドキュメント一式（README / Architecture / API / Database / AI / Roadmap）
- [ ] CI設定（lint / test を回すだけの最小構成） — ワークフロー自体(`ci.yml`)はTask001から存在。
      Task003でテスト本体(`backend/tests/`)を初めて追加したため、`pytest`は理論上テストを
      収集できるはずだが、GitHub Actions上での実行そのものはCEO側の初回PR/pushで初めて確認できる。
      `ruff check`もClaude環境では未実行(ruff未導入)。
- [ ] `.env.example` の整備

## Phase 1 — 最小疎通
- [ ] FastAPI: ヘルスチェックエンドポイントのみ実装 — コード自体はTask001から存在(`GET /health`)。
      Claudeはfastapi未導入のため起動確認はできていない(Task003)。
- [ ] Flutter: 空のMaterial3アプリが起動し、Backendのヘルスチェックを叩けることを確認 —
      Task003でHomeScreen起動へ進んだため、この「空のプレースホルダー画面」というマイルストーン自体は
      追い越した形になる。ヘルスチェック疎通そのものは依然未確認。
- [ ] Supabase: プロジェクト作成・接続情報の確認のみ（テーブルはまだ作らない）

## Phase 2 — 認証
- [ ] Supabase Authを用いたログイン/サインアップ
- [ ] FastAPI側でのJWT検証middleware

## Phase 3 — JSON UI レンダリングエンジン
- [x] `shared/schemas/` にJSON UI Schemaの初版を定義 — v1.0として確定、
      FORGE-MILESTONE-002 PHASE1でv1.1へ拡張(6→12 Widget)。
- [x] Flutter `json_ui/` にレンダラーと最小Widget Registry（text, button, columnなど）を実装 —
      **CEO実機で実測済み**(FORGE-RUNTIME-003完了報告: `flutter analyze` No issues found!、
      `flutter test` 103/103 PASS、Chrome実機でHome→Confirm→Generated Screen→
      チェックリスト操作まで成功)。FORGE-MILESTONE-002 PHASE2でRegistry機構と
      Widget実装を分離し、6 Widget追加(heading/checkbox/card/list/divider/form)。
      この拡張後の`flutter analyze`/`flutter test`はClaude環境では未実行
      (Immediate Next Task参照)。
- [ ] Backendに `apps` / `app_versions` テーブルを作成し、JSON Schemaを保存できるようにする —
      未着手(Supabase未接続のまま)。

## Phase 3.5 — Template System / Language v1.1（FORGE-MILESTONE-002、新規）
- [x] Language v1.1(6 Widget追加、Validator多バージョン対応) — Python側135件・
      Dart側(未検証)のテストを整備。
- [x] Template System(Checklist/Memo/Form) — Python/Dart双方に実装、
      `docs/spec/MOCK_GENERATOR_CONTRACT.md`で機械比較済み。
- [x] Mock Generator v2(12カテゴリ、家事/アンケート/メモを追加)。
- [ ] CEO実機での`flutter analyze`/`flutter test`/Chrome確認 — 未実施
      (Immediate Next Task参照)。

## Phase 4 — AI連携
- [ ] `/api/v1/ai/generate` エンドポイント（会話 → JSON UI Schema） —
      Task003で実装(ただし本物のAIではなくDeterministic Mock Generator。
      `backend/app/ai/generators/mock_generator.py`)。ルーター層(FastAPI)は
      Claude環境で未実行・未検証。呼び出される側の生成ロジック自体は
      `python -m unittest` で検証済み(26/26件合格、Validatorとの結合含む)。
- [x] JSON Schemaバリデーション — Task003で実装・検証済み
      (`backend/app/ai/validators/schema_validator.py`、19/19件合格)。
- [ ] エラー時のフォールバック処理 — クライアント側の表示Fallback(未知Widget等)は
      実装済みだがDart未検証。「不合格だったJSONを自動修復して再提示する」
      Repair Engineそのものは今回のスコープ外(次段階。Migration Plan参照)。

## Phase 5 — CRUD / 実アプリ機能
- [ ] ユーザーが作ったアプリの一覧・編集・削除
- [ ] `_template_feature/` を複製して最初の実featureを追加

## Phase 6 以降 — 拡張機能
- [ ] AI Memory（会話履歴からの長期記憶） — インターフェース設計のみ完了
      (`backend/app/ai/foundation/interfaces.py` の`Memory` Protocol、
      FORGE-MILESTONE-002 PHASE6)。実装は未着手。
- [ ] AI Improve（既存アプリの自動改善提案）
- [x] Template（雛形の再利用） — FORGE-MILESTONE-002 PHASE4で実装
      (`docs/spec/TEMPLATE_SPEC.md`参照)。Checklist/Memo/Formの3種。
- [ ] Marketplace（アプリ/テンプレートの共有・売買） — 未着手(禁止事項)
- [ ] Plugin（サードパーティ拡張） — `PluginRouter` Protocolの設計のみ完了、実装は未着手
- [ ] Team（組織・共同編集）

---

各フェーズは前フェーズの土台を壊さないことを前提とする。
特にPhase 3で定義するJSON UI Schemaは、Marketplace/Plugin/Templateが
将来これに依存するため、破壊的変更は慎重にバージョニングして行う
（`shared/schemas/` にバージョンごとのSchemaを残す）。

Task003（Prototype統合・最初の縦の一本）で何が「書かれた」/「検証済み」かの詳細は
`docs/tasks/task003.md` と `docs/DECISIONS.md` を参照。本ファイルのチェックは、
Claudeが実際に実行して確認できたものだけに`[x]`を付けている
（コードが存在するが未実行のものは`[ ]`のまま注記で状況を残した）。

## Phase 7 — Conversation Readiness(FORGE-CONVERSATION-READY-001、2026-08-12)

「困りごとを話す → 必要最小限だけ質問 → 自然にToolが現れる →
会話で育てる」を一本通すための、Conversation Engineの意思決定強化。

**完了**:

* `MAX_CONVERSATION_TURNS`による強制BUILDの廃止(ターン上限は質問戦略の
  閾値へ変更)。
* `ConversationReadiness`(5値)とPolicy層(`conversation_policy.py`)の新設。
* Question Policy(blocking / high / low / cosmeticのimpact分類、
  繰り返し質問の抑止)。
* CONFIRMのConversation Policyへの正式統合(外部作用・不可逆操作)。
* Unknown / Assumptionへの`reason`付与。
* BUILD失敗時のASKフォールバック(理解段階の失敗のみ)。
* 「はい、どうぞ」Moment(Frontend)。
* Conversation Golden Test / Conversation Metrics。

**未着手(次段階)**:

* Voice(STT/TTS)のAdapter接続。Product Logic側は完成しており、
  Voice未実装でも成立する状態にしてある(指示書11章の優先順位に従い、
  意図的に後回しにした)。
* Metricsの外部分析基盤への送出(現状はプロセス内メモリのみ)。
* Readiness判定の実データによる調整(現在は決定的なルールベース)。
