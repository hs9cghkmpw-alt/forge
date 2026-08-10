# ADR-011: Why FORGE IR Is Introduced Incrementally (3 Domains Only)

**Status:** Accepted
**Ref:** FORGE v0.5「FORGE IR v1 Architecture Proposal」6章Migration
Plan → FORGE v0.6「FORGE IR v1 Minimal Implementation」

## Context

FORGE IRは、`ApplicationPlan`とForge Languageの間に新しい層を追加する、
アーキテクチャ上の大きな変更である。既存のCheckist単一画面Domain
(shopping/task_management/diary/survey/schedule/inventory)は、
Template-aware Compiler Stage1導入時と同様、大量の既存テスト
(このADR作成時点でforge_ai 285件・backend 307件)を持つ、実績のある
経路である。

## Decision

**FORGE IRは、Template-aware Compiler Stage1で新設した3 Domain
(fishing_log/household_budget/habit_tracking)にのみ適用し、既存
6 Domainは既存の`Compiler`(Checklist単一画面)経路をそのまま維持する。**

`pipeline_orchestrator.py`が、`domain_category`が
`ir_generator.SUPPORTED_DOMAIN_CATEGORIES`に含まれるかどうかで、
明示的に経路を分岐する。`Compiler`クラス自体は、Stage1で一時的に
追加した分岐ロジックを撤去し、Stage1導入前と同じ「Checklist単一画面
専用」という単一の責務へ戻す。

## Alternatives

- **全Domainを一斉にFORGE IR経由へ移行する**: 却下。既存6 Domainの
  Checklist出力は、IRのEntity/View/Action語彙でも表現できるはずだが
  (`FORGE-IR-V1-PROPOSAL.md`6.3節Phase3で将来検討事項として言及)、
  一斉移行は既存テスト全件への影響範囲を広げ、「既存テストの削除・
  弱体化は禁止」という制約の遵守を難しくする。今回のスコープでは
  リスクに見合わない。
- **FORGE IRを新規Domain専用の永続的な別経路とし、既存Domainは
  将来も統合しない**: 採用しない(明示的な決定ではないが、
  `FORGE-IR-V1-PROPOSAL.md`6.3節Phase3で「既存DomainもIR経由へ統一
  することを将来検討する」と明記しており、今回の3 Domain限定は
  「最終形」ではなく「まず安全な範囲で導入する」という意味である)。

## Consequences

- `Compiler`(Checklist経路)と`ForgeLanguageCompiler`(IR経路)という、
  意味的に重複する2つのCompilerクラスが、当面併存する。この重複は、
  Phase3(既存Domainの統合)が実施されるまでの、意図した過渡的な状態
  である。
- `pipeline_orchestrator.py`に、2つの経路を選択する分岐ロジックが
  残る。将来Phase3で全Domainが統合されれば、この分岐は撤去できる。
- 対象3 Domain以外への影響が実質ゼロであることを、既存テスト全件
  (forge_ai・backend)の再実行で継続的に確認する運用とする。

## Revisit Conditions

- 対象3 Domainでの運用が安定し、IRの抽象化がForge Language以外への
  展開にも耐えうると判断できた時点で、Phase3(既存6 Domainの統合)へ
  進むかどうかを再評価する。
- `Compiler`/`ForgeLanguageCompiler`の重複が、保守コスト上の負担に
  なっていると判断された場合、Phase3への着手を前倒しする。
