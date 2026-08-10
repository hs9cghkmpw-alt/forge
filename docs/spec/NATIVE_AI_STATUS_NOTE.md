# Native AI Foundation / MILESTONE-004 — 現状メモ(M003.1レポートから分離)

**この文書はFORGE-MILESTONE-003.1の成果物ではない。** CEOレビューで
「M003.1なのにAI Runtimeまで話が飛んでいる。別章ではなく別Issue・別Taskとして
切り離すこと」というご指摘を受け、M003.1レポート本体から分離した。

---

## 1. 今回CEOがChrome実機確認した内容との関係

**無関係。** CEOがこれまで実機確認した生成フローは、すべて
`MockAppGenerationRepository` → Mock Generator → Forge Language JSON →
Dart Runtimeという経路であり、`backend/app/ai/runtime/`・
`backend/app/ai/native/`配下のいずれのコンポーネントも、この経路から
一度も呼び出されていない。

両ディレクトリには、それぞれ現状を明示する`README.md`を新設した
(`backend/app/ai/runtime/README.md`・`backend/app/ai/native/README.md`)。
要点は「Status: EXPERIMENTAL — NOT CONNECTED — NOT USED IN PRODUCTION
PATH」。

## 2. MILESTONE-004関連コードについて(事実関係)

最終検証中に、`backend/app/ai/runtime/intent_parser.py`・
`native_ai_runtime.py`・`template_engine.py`・`template_selector.py`、
および`backend/app/ai/native/`配下のファイル群を確認した。

`docs/tasks/task019.md`・`CHANGELOG.md`に、「Task019 —
FORGE-MILESTONE-004: Native AI Phase-1（Intent Engine）」という、
正規の形式で番号付けされたエントリが既に存在することを確認した。
Claudeが現在参照できる会話履歴の中には該当する依頼文そのものは
見当たらないが、タスク番号の連続性・CHANGELOG記載の形式が、これまでの
正規タスクと完全に一致するため、実際には正規のCEO依頼に基づいて
別のタイミングで処理されたタスクである可能性が高いと判断している。

実際に動作し合格しているコード・テスト(27件、`test_native_ai_phase1.py`)を、
出所の確認が完全にはできないという理由だけで削除することはしなかった。

## 4. 更新(2026-07-14): FORGE-MILESTONE-004として forge_ai/ を正式採用、
      および「Native AI Phase-1」の由来を確認(訂正)

CEOから「FORGE-MILESTONE-004を開始してください。目的はForge AI v0.1
（Cognitive Engine）の基盤構築です。Domain Model・World Model・
Meaning Model・Intent Model・Plannerを実装してください」という、
本メモが扱う内容と正確に一致する依頼を受けた。

`forge_ai/`が依頼内容と完全に一致する実装(Domain/World/Meaning/Intent/
Planner、LLM非依存、Mock Provider、80テスト全合格)を既に持っていたため、
ゼロから再実装するのではなく、既存実装を検証・強化した上で
今回の依頼の正式提出物として採用した。詳細は
`forge_ai/docs/DESIGN_DECISIONS.md` D6参照。

**訂正**: 本メモの2章で「由来を追跡できない」としていた
`backend/app/ai/runtime/`内の一部ファイル(intent_parser.py等)は、
`docs/reports/FORGE-MILESTONE-004-report.md`(2026-07-13付、
「Native AI Phase-1（Intent Engine）」)という正規の報告書、および
`docs/DECISIONS.md` D50〜D55・`TECH_DEBT.md` TD20〜TD22で、既に
文書化されていることを確認した。この報告書は`forge_ai/`とは別の、
`backend/app/ai/runtime/`を拡張する内容であり、今回CEOが依頼した
「forge_ai/相当のDomain/World/Meaning/Intent/Planner」とは異なる。

**つまり「FORGE-MILESTONE-004」という名前が、2つの異なる内容
(a. Native AI Phase-1 = backend/app/ai/runtime/の拡張、
b. 今回の依頼 = forge_ai/相当の基盤構築)に対して使われている。**

**未解決のまま残っている点**: `backend/app/ai/native/`の由来は
依然として確認できていない。`forge_ai/`と「Native AI Phase-1」の
統合方針、および「FORGE-MILESTONE-004」という名前の重複整理は、
CEO判断が必要な事項として残す(詳細は今回のFORGE-MILESTONE-004-report.md参照)。



## 5. 最終更新(2026-07-14): Architecture Freeze確定、番号重複を解消

CEOレビューを受け、`docs/spec/FORGE_AI_ARCHITECTURE_V1.md`という
Architecture Decision Recordを新設し、以下を正式に確定した。

- **M004** = `forge_ai/`(Forge AI Core)のみ。
- **M005** = `backend/app/ai/runtime/`(Backend AI Integration、
  旧称「Native AI Phase-1」)。
- **M006以降(未定)** = `backend/app/ai/native/`(Experimental、
  CEO承認なしに変更しない)。

本メモ(NATIVE_AI_STATUS_NOTE.md)が3〜4章で報告していた「未解決事項」
「番号重複」は、`FORGE_AI_ARCHITECTURE_V1.md`で正式に解消された。
今後、Native AI関連の設計判断は同ADRを正典として参照すること。
