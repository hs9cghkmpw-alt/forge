# ADR-010: Why FORGE IR Is Introduced Between ApplicationPlan and Forge Language

**Status:** Accepted(Phase1〜2のみ、`FORGE-IR-V1-PROPOSAL.md`参照)
**Ref:** FORGE v0.5「FORGE IR v1 Architecture Proposal」承認 →
FORGE v0.6「FORGE IR v1 Minimal Implementation」

**注記(ADR番号について)**: この提案書自体は「ADR-001」として指示
されたが、`docs/adr/`には既にADR-001〜ADR-009(Cognitive Architecture
関連、無関係な既存の決定群)が存在するため、既存の番号と衝突しない
よう、続き番号(ADR-010〜012)へ採番し直した。

## Context

Template-aware Compiler Stage1(FORGE v0.3)で、`Compiler`クラスへ
`DomainField`/`DomainDataModel`/`_DOMAIN_DATA_MODELS`という「データ
モデル定義」と、「Forge Language(Widget/Action/State)への変換ロジック」
の両方を同居させた。CEOのレビュー(FORGE v0.5の背景説明)により、
「CompilerがUIを知りすぎている」こと、将来Flutter以外のプラット
フォーム(React/SwiftUI/Jetpack Compose等)への展開を見据えると、
この2つの責務は分離すべきであることが指摘された。

## Decision

**`ApplicationPlan`と`ForgeDocument`(Forge Language)の間に、
プラットフォーム非依存の中間表現FORGE IRを新設する。**

```
ApplicationPlan → IRGenerator → ForgeIR → ForgeLanguageCompiler → ForgeDocument
```

FORGE IRは、Entity/Field/View/Action/Event/NavigationGraphという、
「アプリが何をするか」を表現する語彙のみを持ち、Widget名・state_ref・
具体的なAction JSON形式といった「Flutter Runtime上でどう実現するか」
は一切含めない(ADR-012)。

## Alternatives

- **`Compiler`クラス内でDomain Data Model定義とForge Language生成
  ロジックを分離するだけに留める(独立した中間表現は作らない)**:
  却下。クラス内でモジュールを分けても、「他のプラットフォームへの
  出力」という将来の拡張ニーズには応えられない。中間表現として明確に
  独立させることで、複数の「コンパイル先」を対等に追加できる構造に
  なる。
- **`ApplicationPlan`自体を拡張し、Entity/Field相当の情報を直接
  持たせる(IRという新しい層を作らない)**: 却下。`ApplicationPlan`は
  Domain分類・画面構成計画など、既に多くの責務を持っており、これ以上
  「データモデルの型情報」まで持たせると、Planner自体の責務が肥大化
  する。IRという別層に切り出すことで、Plannerの責務(何を作りたいかの
  大まかな計画)と、IR Generatorの責務(具体的なデータモデルへの変換)
  を分離できる。

## Consequences

- 新しいDomain Data Model(Entity定義)を追加する際、`ir_generator.py`
  だけを変更すればよく、`compiler.py`(Forge Language生成ロジック)には
  触れない、という開発体験が実現する。
- 将来Flutter以外のターゲットを追加する際、`ForgeLanguageCompiler`と
  対等な新しい「Compiler Backend」を1つ追加するだけで済む
  (`FORGE-IR-V1-PROPOSAL.md`7章)。
- 一方で、層が1つ増えることによる複雑さの増加は許容している
  (ADR-011「段階的導入」で、このコストをPhase1〜2(対象3 Domainの
  み)に限定することで緩和する)。

## Revisit Conditions

- Phase2(対象3 Domain)の運用を通じて、IRが実際に「Forge Language
  以外のターゲットを見据えた抽象化」として機能しているかを再評価する。
  もし実際にはFlutter固有の概念がIRへ漏れ出し続けるようであれば
  (ADR-012のガバナンスが機能していない場合)、IR層の意義そのものを
  再検討する。
