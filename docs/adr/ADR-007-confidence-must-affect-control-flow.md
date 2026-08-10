# ADR-007: Why Confidence Must Affect Control Flow

**Status:** Proposed（設計フェーズ、未実装）
**Ref:** FORGE-MILESTONE-006

## 2026-07-21追記(Task042-1実装、CEO承認済み段階計画の第1段階)

本ADRの実装が、`Task042`として3段階(Task042-1〜3)に分けて着手された
(`docs/tasks/task042.md`・`FORGE-TASK042-ADR007-INVESTIGATION-
PLAN.md`参照)。**Task042-1(観測専用のConfidenceRecord・overall_
confidence導入)のみ完了しており、本ADR自体のStatusはまだ`Proposed`
のまま据え置く**(制御フローはまだ何も変わっていないため)。

- Task042-1: `ConfidenceRecord{value, basis}`・`OverallConfidence`
  (`forge_ai/core/orchestration/cognitive_types.py`)、
  `compute_overall_confidence()`(`forge_ai/core/orchestration/
  confidence.py`)を新設。DecisionTraceへ観測記録するのみで、
  下記Decisionが求める制御フロー(`if`分岐)へはまだ一切使っていない。
- Task042-2(未着手): CEOから「本ADRが提案する0.5/0.8という単一閾値
  への単純置換ではなく、既存の3信号モデル(intent confidence・
  domain coverage・score margin)を内部要素として残しつつ、
  `overall_confidence`と比較実験できる状態を作る」という方針が
  明示されている。この方針が固まり、実際に制御フローへ組み込まれた
  段階で、本ADRのStatusを`Accepted`/`Implemented`へ更新する。

  **Phase B完了(2026-07-21)**: `ShadowJudgment`(現行モデル・
  overall_confidenceモデルの判定を並行計算し、DecisionTraceへ観測
  記録するのみ)を実装した。Golden Test全42件での比較の結果、一致率
  100%(不一致0件)だった。**制御フローはまだ一切変わっていない**
  ため、本ADRのStatusは引き続き`Proposed`のまま。実際の判定ロジック
  置換(Phase C)は、比較データがさらに蓄積され、別途CEO承認を得て
  からとする。詳細は`docs/tasks/task042.md`・
  `FORGE-TASK042-2-SHADOW-COMPARISON-REPORT.md`参照。

  **評価フェーズ完了・Phase Cを開始しない理由(2026-07-22)**:
  Task042-2 Evaluation Report(`FORGE-TASK042-2-EVALUATION-REPORT.
  md`)の結論として、Task042をここで「評価フェーズ完了」として
  一区切りとし、Phase Cへは進まないことを決定した。

  2026-07-22時点でPhase Cへ進まない理由は、「閾値が未確定だから」
  ではなく、**「モデルの構造自体に未解決の設計課題があるから」**
  である。具体的には、`score_margin`という、現行モデルが実際に
  依拠しているsignalが、`overall_confidence`の計算に一切反映
  されていない。この状態で閾値だけを調整しても、`score_margin`が
  効くべき場面(僅差判定)を新モデルが構造的に見逃す、という問題は
  解消されない。また、Golden Test corpus(比較に使った42件)を
  分析した結果、**低confidence領域(実際に確認要求になりうる入力)
  を一切カバーしていない**ことが判明した——42件全てが
  `high_confidence`または`medium_band`に分類され、一致率100%という
  結果は、実際には「低confidence領域を一度も試していない」ことの
  裏返しでしかなく、Phase Cへ進む根拠として使うには不十分である。

  Phase C開始条件(`FORGE-TASK042-2-EVALUATION-REPORT.md`3章)として、
  (1)`score_margin`の統合方針の確定、(2)低confidence領域を含む
  テストデータの拡充、(3)Task042-3(複数ApplicationPlan候補保持)
  完了によるmedium_band対応の確立、(4)十分な一致率、(5)実運用
  データでの追加検証、の5点を明文化した。次のステップとして、
  Task042-3(複数候補保持)の設計・実装を先に進めることを提言した。
- Task042-3(未着手、別マイルストーンへの切り出しを検討中):
  0.5〜0.8帯の「複数ApplicationPlan候補保持」は、Planner・Critic・
  Orchestrator・DecisionTraceの全てに影響する規模であり、本ADRの
  実装というより独立した機能追加に近いという判断がCEOから示されて
  いる。

## Context

各認知段階(3章)が信頼度(confidence)を算出できても、それが単なる
「表示用の数値」に留まるなら、Human Override(2.6節)・Ambiguity
Detection(4章)の実効性が失われる。低いconfidenceのまま断定的な
設計を進めてしまうことは、Failure Mode「Confidence過信」(17.13節)
に直結する。

## Decision

**Confidenceは、パイプラインの分岐(制御フロー)に実際に影響を与える
ものとして設計する(14章)。ただし単独の閾値表としてではなく、4.3節の
3段階優先順位の一部として扱う(2026-07-15、CEO監査により統合)。**

優先順位(4.3節):
1. Privacy/Safety/Permission関連のHIGH ambiguidadeは、confidenceの
   値に関わらず必ず確認する。
2. 上記に該当せず`overall_confidence`が0.5未満の場合、原則として確認する。
3. 低リスクかつ後から安全に変更可能な用途に限り、確認を経ずGenericへ
   仮設計してよい。

具体的な閾値と挙動(14.2節):
- 0.8以上: そのまま継続。
- 0.5〜0.8未満: 複数案を保持し仮設計(Ambiguity DetectionのMEDIUMと
  同じ扱い)。
- 0.5未満: 上記優先順位2/3の適用(原則確認、低リスク時のみGeneric)。

**2026-07-15の修正**: 以前は「0.3〜0.5未満はGenericへ落とす」
「0.3未満は確認する」という2段階の追加閾値を持っていたが、これは
4.3節(Ambiguity Detection側)の「confidence 0.5未満はHIGH」という
基準と0.3〜0.5の範囲で矛盾していた。0.3という閾値を廃止し、0.5未満は
一貫して「優先順位2(原則確認)、ただし優先順位3(低リスク)の
carve-outがあればGeneric仮設計可」という1つのルールへ統合した。

さらに、confidenceは根拠(`basis`)を伴わなければならず、根拠の無い
confidence引き上げを禁止する(14.3節、17.2節「Intent過剰推定」への
対応と共通)。

## Alternatives

- **Confidenceを算出はするが、常に処理を続行し、Confidenceは
  ログ・診断情報としてのみ扱う**: 却下。この設計では、低confidence
  のまま断定的な設計が進んでしまうケース(Confidence過信、17.13節)を
  構造的に防げない。「単に数値を出すだけでなく、根拠を持たせること」
  という明示的な要求とも整合しない。
- **Confidenceに応じた分岐を、実装者の裁量に委ねる(段階ごとに
  バラバラの閾値・挙動にする)**: 却下。段階をまたいで一貫した挙動
  (LOW/MEDIUM/HIGHという共通言語)を持たせないと、ユーザー体験が
  段階ごとに不統一になり、説明可能性(ADR-005)も損なわれる。
- **Confidence閾値とAmbiguity Detectionの重大度を、それぞれ独立した
  判定として並存させる(本ADRの旧版)**: 却下(2026-07-15訂正)。
  0.3〜0.5の範囲で、どちらの判定が優先されるか未定義になり、CEO監査で
  矛盾として指摘された。両者を1つの優先順位(4.3節)へ統合した。

## Consequences

- 閾値(0.8/0.5)は、実運用データが無い現時点での提案であり、
  実装後の運用データに基づく再調整が前提となる(14.2節の「事実と
  推測の分離」)。閾値変更自体は軽微に見えても、Forge体験の一貫性に
  関わるため、変更にはCEO承認を要件とする(17.14節と同じ理由)。
- 低confidence時の「ユーザーへの確認」フロー(Human Confirmation/
  Escalation、3.12節)を、UXとしてどう提示するか(Flutter側の対応)は、
  本ドキュメントのスコープ外であり、別途M007以降の実装フェーズで設計する。

## Revisit Conditions

- 実際の運用データで、閾値が過度に保守的(Genericへ落ちすぎる、
  17.14節)、または過度に楽観的(誤った断定が多い、17.13節)と
  判明した場合、CEO承認のもとで閾値を調整する。
