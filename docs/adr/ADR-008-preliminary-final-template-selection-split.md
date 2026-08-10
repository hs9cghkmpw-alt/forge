# ADR-008: Why Application Planning and Template Selection Are Split Into Preliminary/Final Phases

**Status:** Superseded in part（下記「2026-07-15追記」参照）
**Ref:** FORGE-MILESTONE-006（2026-07-15、CEO実物監査により新設）

## 2026-07-15追記(2回目、CEO実物監査(4回目)による最終確定)

前回の追記(直後の節)で「CEOが提示した15段階の並び」と書いたが、
これも暫定的な数え方だった。最終的に、`docs/spec/
FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` Task3.3で「14 Transformation
Stage + 1 Terminal Outcome(M004側)+ 3 M005 Post-processing Stage」
という、性質を区別した数え方へ確定した。「16段階」「15段階」という
表記はいずれも撤回する。

また、「Final選択がPreliminary候補と著しく異なる場合の再計画」の
具体的な実現方法も確定した。**当初「同じ入力でApplication Planningを
再実行する」という設計だったが、決定的な実装であれば同じPlanが
再生成されるだけで無意味であるため、この不一致を「合成Critic Issue」
として構築し、Cognitive Revision(`revision_engine.revise()`)へ
一本化した。** カウンタ・上限を共有するという決定自体は変わらないが、
「何を渡して再計画するか」が、以前の「同じ入力をそのまま渡す」から
「不一致の内容を新しい情報として渡す」へ具体化された。

## 2026-07-15追記(1回目、FORGE-MILESTONE-007 PREPARATION、CEO実物監査(3回目)による訂正)

**下記Decisionの「Preliminary Pattern Candidatesを、Application
Planningの内部フェーズとして隠す(トップレベル段階として数えない)」
という部分は撤回する。**

CEOの実物監査により、「Preliminary選択をApplication Planner内部へ
隠すことは禁止する」という指摘を受けた。Preliminary Pattern
Candidatesは、`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md`
Task3.3が示す通り、**Orchestratorが明示的に呼び出す、独立した可視の
呼び出し**(`template_selector.select_preliminary(...)`)として扱う。
「16段階に収めるために内部へ隠す」という下記Alternatives第3項の判断は
撤回し、CEOが提示した15段階の並び(Preliminary Pattern Candidatesを
含む)をそのまま採用する。

**維持される部分**: Final選択がPreliminary候補と著しく異なる場合の
再計画が、Cognitive Revisionと**同じカウンタ・上限を共有する**という
決定(下記Decision後半)は、そのまま維持する。これは今回の訂正の
対象ではない。

以下、当初のContext/Decision/Alternatives/Consequencesは、判断の
経緯を残すため元のまま保持する。

---

## Context

`docs/spec/FORGE_COGNITIVE_ARCHITECTURE_V2.md`の旧版(3.8節・3.9節)は、
Application Planning → Template Selectionという一方向の関係として
記述していた。しかしApplication Planningの責務(9章)は「Domain
Registryの`recommended_patterns`」(5.1節、Template Familyへのヒント)
を既に参照する設計になっており、Template Selectionが独立した後続の
決定であるという建前と矛盾する、隠れた循環依存があった。CEOの実物監査
でこの点を指摘された。

## Decision

**Application Planningを2つの内部フェーズへ分割し、Template Selectionを
「Final Template Selection」として明示的に再定義する。**

```
Preliminary Pattern Candidates(Application Planningの内部フェーズ1)
  ↓ Domain・Intent・RequirementSetのみから大まかに絞り込む(まだ画面数等は未確定)
Application Planning本体(内部フェーズ2)
  ↓ Preliminary候補をヒントに、画面構成・State・Action等を確定する
Final Template Selection(3.9節、独立した段階)
  ↓ 確定したApplicationPlanの画面数・編集要否・履歴要否等(10.2節の9基準)で最終決定
Design Critic
```

Preliminary Pattern Candidatesはトップレベルのパイプライン段階として
数えない(Application Planningという1段階の内部フェーズとして扱う。
3章の16段階カウントに影響しない)。

**Final選択がPreliminary候補と著しく異なる場合の扱い**: この場合、
Application Planningの再実行が必要になりうるが、これを独立した新しい
ループとして作らない。Cognitive Revision(3.11節、12章)と**同じ
カウンタ・上限を共有する**扱いとする(12.4節「二重ループ防止」の対象を、
Cognitive Revision⇔Schema Repairの2つから、Planning⇔Template
Selectionを含む3つ目の潜在ループへ拡張する)。

## Alternatives

- **Application PlanningとTemplate Selectionを完全に独立させ、
  Application PlanningはDomain Registryの`recommended_patterns`を
  一切参照しない**: 却下。Domain Registry(5章)が既に持つ
  `recommended_patterns`という有用なヒントを使わないのは非効率であり、
  「Rule Before Prompt」(ADR-003)の精神(決定的に分かることは決定的に
  使う)にも反する。
- **Template SelectionをApplication Planningより前に完全に確定させる
  (旧: Template Selection → Application Planningという順序へ入れ替える)**:
  却下。10.2節の評価基準(画面数・編集要否・履歴要否・集計要否・遷移
  要否・検証要否等)の多くは、実際にApplicationPlanが確定していないと
  評価できない(画面数はApplication Planningの結果そのものであるため)。
  Template SelectionをPlanningより前に完全化することはできない。
- **Preliminary Pattern Candidatesを、独立したトップレベルの
  パイプライン段階(17段階目)として追加する**: 検討したが不採用。
  CEO指摘の「16段階への統一」という要求と、責務の性質(まだ何も
  確定していない、Application Planningの準備作業に過ぎない)を
  踏まえ、独立段階ではなくApplication Planningの内部フェーズとする
  ほうが、責務の実態に即していると判断した。

## Consequences

- Application Planningの出力(`ApplicationPlan`)は、Preliminary候補を
  `preliminary_template_candidates`として保持したまま次段階へ渡す
  必要があり、9章の`ApplicationPlan`構造にこのフィールドを追加する
  ことが実装時の前提になる。
- Final Template SelectionがPreliminary候補と異なった場合の
  再計画は、Cognitive Revisionのカウンタ(既定上限2回)を消費する。
  実装時、「Planning再実行」と「Critic起因のRevision」を同じカウンタで
  管理するロジックが必要になり、実装の複雑さは増すが、二重ループを
  防ぐためのコストとして許容する。
- テスト設計上、「Preliminary候補とFinal選択が一致するケース」
  (`docs/examples/`の大半)と「一致せず再計画が発生するケース」の
  両方をカバーする必要がある。

## Revisit Conditions

- 実装後、Preliminary Pattern Candidatesの絞り込みが実際にはほとんど
  効果を持たず(常にFinal選択と一致する、またはほぼ意味のある絞り込みに
  ならない)と判明した場合、この2フェーズ構造自体の簡略化を検討する。
- Planning⇔Template Selectionの再計画が頻発し、Cognitive Revisionの
  カウンタを常に消費してしまう場合、Preliminary Pattern Candidatesの
  精度(Domain Registryの`recommended_patterns`の質)を先に見直す。
