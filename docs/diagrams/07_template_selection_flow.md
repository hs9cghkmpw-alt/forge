# Diagram 7: Template Selection Flow(2026-07-15、FORGE-MILESTONE-007
PREPARATION CEO実物監査(3回目)により、Preliminaryを独立ノードへ再修正）

**2026-07-15追記**: 当初、Preliminary Pattern CandidatesをApplication
Planningの内部フェーズとして図示していたが、CEOの実物監査により
「Application Planner内部へ隠すことを禁止する」と指摘され、独立した
可視のノードとして描き直した(ADR-008の該当箇所も参照)。

```mermaid
flowchart TD
    RS[RequirementSet + Intent + primary_domain] --> PRE["Preliminary Pattern Candidates\n(独立ノード。Domain Registryのrecommended_patternsで\n大まかに絞り込む。まだ画面数等は未評価)"]
    PRE --> AP["Application Planning\n(Preliminary候補・World・Requirementsを入力に\n画面/State/Action確定)"]
    AP --> SC["Final Template Selection: 9項目でスコアリング<br/>(Dominant user action, Data lifecycle,<br/>Number of entities, Need for editing,<br/>Need for history, Need for aggregation,<br/>Need for navigation, Need for validation,<br/>Need for multiple users)"]
    SC --> RANK[11 Template Familyへスコア付け<br/>checklist/form/memo/crud/dashboard/<br/>calendar/tracker/catalog/detail_list/<br/>wizard/generic]
    RANK --> GAP{最高スコアと次点の差は<br/>十分大きいか?}
    GAP -->|yes、決定的に決まる| SELECT[Template確定]
    GAP -->|no、僅差| LLM[LLM Tie-Break<br/>候補上位2-3件のみ渡す]
    LLM --> SELECT
    SELECT --> DIFF{Preliminary候補と<br/>著しく異なるか?<br/>differs_from_preliminary}
    DIFF -->|yes| REPLAN["合成Critic Issueとして構築し、\nCognitive Revisionへ引き渡す\n(同じカウンタを消費、ADR-008)"]
    REPLAN --> REVISE[Cognitive Revision: revision_engine.revise]
    REVISE --> AP
    DIFF -->|no| VALIDATE{applicable_when/<br/>not_applicable_when<br/>と矛盾しないか}
    VALIDATE -->|矛盾| FALLBACK[fallback_templatesへ]
    FALLBACK --> SELECT
    VALIDATE -->|OK| DONE[Design Criticへ]

    style LLM fill:#fff3cd
    style SC fill:#e8f4ea
    style RANK fill:#e8f4ea
    style PRE fill:#d1ecf1
    style REPLAN fill:#f8d7da
    style REVISE fill:#f8d7da
```

10章(Template Selection、= Final Template Selection)・3.8節
(Application Planning)・ADR-008に対応。決定的スコアリングが常に
先に走り、LLMは僅差の場合のみ限定的な情報で呼ばれることを図示している
(ADR-003 Rule Before Prompt)。**再計画(赤色ノード)は独立した新しい
ループではなく、Cognitive Revision(図5参照)と同じ試行回数カウンタを
共有する(ADR-008、12.4節「二重ループ防止」の対象拡張)。**
