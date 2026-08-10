# ADR-009: Why run_cognitive_pipeline() Is a Separate Facade, Not a Boolean Flag on run_pipeline()

**Status:** Proposed（設計フェーズ、未実装）
**Ref:** FORGE-MILESTONE-007 PREPARATION（2026-07-15、CEO実物監査(2回目)により新設）

## Context

`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md`の旧版(Task9)は、
既存`run_pipeline()`へ`use_cognitive_pipeline: bool = False`という
引数を追加し、単一の関数内でBoolean分岐する設計を提案していた。

CEOの実物監査により、この設計には欠陥があると指摘された:
`needs_confirmation`(Human Confirmation/Escalation)は、Ambiguity
Detection(M006 3章の2段階目)の直後にも発生しうるが、この時点では
既存`PipelineResult`が必須とする`domain`・`world`・`meaning`・
`intent`・`plan`・`ir`・`quality`のいずれも存在しない。これを
既存`PipelineResult`へ変換しようとすると、存在しない値の代わりに
ダミー値を生成する必要が生じてしまう。

## Decision

**`run_pipeline()`(既存、無変更)と`run_cognitive_pipeline()`
(新規)を、別関数・別戻り値型として完全に分離する。**

- `run_pipeline() -> PipelineResult`: 既存のまま、シグネチャ・戻り値型・
  内部ロジックとも一切変更しない。
- `run_cognitive_pipeline() -> CognitivePipelineOutcome`: 新規。
  `CognitivePipelineOutcome`は`CognitivePipelineSuccess` /
  `CognitivePipelineNeedsConfirmation` / `CognitivePipelineFailed`
  という3つの独立したdataclassのUnionとして定義し、各終了状態が
  **実際に存在する情報だけ**を持つ(9.2節)。**`CognitivePipelineSuccess`
  は`context: CognitiveContext`・`ir: ForgeIRDocument`・
  `initial_quality: QualityScore`の3フィールドのみを持つ(CEO実物監査
  (4回目)により確定。`CognitiveContext`が既に保持する情報
  (`domain_classification`・`world`・`meaning`・`intent`・`plan`等)を
  個別フィールドとして重複保持しない。詳細は`FORGE_M007_
  IMPLEMENTATION_BLUEPRINT.md` Task3.5)。**

段階導入は、Boolean引数による実行時分岐ではなく、M005側の呼び出しコード
(import文・呼び出し箇所)が、どちらの関数を呼ぶかを明示的に切り替える
方式とする(実装時にコード上どちらを使っているかが常に一意に確定する)。

**副次的な決定(CEO指摘3)**: `CognitivePipelineSuccess`は
`initial_quality: QualityScore`を持つ。これはForge IR Compilation
直後、Repair前の値であり、既存M005(`prompt_pipeline.py`)が既に
実装しているRepair後の再評価(Final Quality)とは別物であることを
明記する。この責務分担(M004=Initial、M005=Final)自体は新規の設計
判断ではなく、既存コードに既に実装されている挙動の明文化である。

## Alternatives

- **Boolean Feature Flag(旧設計)**: 却下。上記Context参照。
  「ダミー値を生成してPipelineResultへ変換することは禁止する」という
  CEOの明確な指摘に反する。
- **`PipelineResult`の全フィールドをOptionalにする**: 却下。
  既存`run_pipeline()`の呼び出し元(既存80テスト・将来のM005)が、
  「常に埋まっているはずのフィールド」への依存を失い、None チェックが
  至る所に必要になる。既存の`run_pipeline()`自体は変更しないという
  今回の決定と両立しない(既存関数の戻り値型を変えることになるため)。
- **`CognitivePipelineOutcome`を単一dataclassとし、全フィールドを
  Optionalにする**: 却下。3つの終了状態それぞれの「本来存在するはずの
  情報」と「存在しないはずの情報」の区別があいまいになり、ダミー値
  問題と同種の混乱を生む。3つの独立したdataclassのUnionとする方が、
  型システム上も「success時にはconfirmation_requestが無い」ことが
  構造的に保証される。

## Consequences

- `run_cognitive_pipeline()`の呼び出し元(将来のM005・Golden Test)は、
  `isinstance()`による分岐処理を書く必要がある(単一の戻り値型を
  `if result.success:`のように判定するより、わずかに複雑になる)。
- `run_pipeline()`と`run_cognitive_pipeline()`という、概念的に近い
  2つの関数がforge_ai/に併存することになり、将来的にどちらを「正」と
  するか(またはいつ`run_pipeline()`を廃止するか)を、別途決定する
  必要がある(9.4節、CEOへの確認事項2)。
- M005側が実際に`run_cognitive_pipeline()`を呼ぶよう切り替えるには、
  M005側のコード変更(import文・呼び出し箇所)が必要になる。この変更
  自体は今回(forge_ai/側の設計)のスコープに含まれず、CEO承認を得た
  別Taskとして実施する。

## Revisit Conditions

- `run_cognitive_pipeline()`が実運用で安定し、M005が完全にこちらへ
  移行した場合、`run_pipeline()`(旧Facade)の廃止時期を検討する。
- `CognitivePipelineOutcome`の3分岐(success/needs_confirmation/
  failed)だけでは表現しきれない終了状態(例: 部分的な成功)が
  実装時に必要になった場合、Union型の拡張を検討する。
