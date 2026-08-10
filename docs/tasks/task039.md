# Task039 — FORGE-MILESTONE-007 Phase 1.2: Meaning Model導入

## 依頼内容
M007 Phase 1.1の実装・テスト結果を前提として、Meaning ModelをCognitive
Pipelineへ正式に追加することを依頼された。複数画面化へは進まず、
入力文の意味を構造化し、その結果をRequirement Extraction・
Application Planning・Decision Traceへ実際に接続するところまでを
対象とした。対応対象として、共有・写真/気分・期限/優先度・在庫低下・
回答後一覧・毎週月曜日という修飾条件を含む6入力が指定された。

## 行ったこと
- `SemanticUnit`/`ExtractedMeaning`(Cognitive専用)を`cognitive_types.py`
  へ新設した。Legacy`meaning_model.py`の`ExtractedMeaning`とは、
  必須の第1フィールドが異なる(raw_text vs summary)ため別クラスとした。
- `CognitiveMeaningExtractor`を実装し、日本語キーワード辞書による
  決定的な抽出(Actor/Entity/Action/Constraint/Preference/Temporal/
  State/Evidence span)を行った。
- `RequirementExtractorProtocol`をBlueprint本来の3引数
  (meaning, world, intent)へ復元し、Meaning由来の情報をFunctional/
  Data/Validation/Schedule/State/Permission Requirementへ変換した。
- `Requirement.derived_from`を新設し、ApplicationPlannerが「World由来の
  基本要件」と「Meaning由来の追加要件」を区別し、Meaning由来の
  mandatory要件のみを自動的にPlanへ反映するようにした(下記の実装中
  発見事項参照)。
- `DesignCritic`へ`intent_meaning_fidelity`軸を追加し、Meaning由来の
  mandatory要件が未反映の場合にblockingとした。
- Unit Test(Meaning抽出11件・Requirement変換7件)・Integration
  Test(6件)・Golden Test(複雑入力6例、4件)を追加した。
- Forge AI全テスト(192件)・Backend全テスト(265件)を実行し、
  既存回帰が無いことを確認した。

## 実装中に発見・修正した設計上の問題
当初、全てのmandatory要件(target_ref/operation_ref付き)を無条件で
Plannerが自動反映する設計にしたところ、Phase 1.1で追加した回帰テスト
(「実際にPlanへ反映されていないrequirementはunassignedのままになる」
ことを検証するテスト)が失敗した。原因は、テスト用に意図的に構築した
「Planに存在しないaction」を持つ要件までもが自動反映されてしまい、
「反映されていないことを検出する」というテストの前提そのものが
成立しなくなっていたことだった。`Requirement.derived_from`フィールドを
新設し、Meaning由来(`"meaning"`)の要件のみを自動反映の対象とすることで、
Phase 1.1の機械判定機能とPhase 1.2のMeaning反映機能を両立させた。

## 変更理由
CEOの明示的な依頼に基づく。既存コードへの変更(CognitiveContext・
CognitiveDependencies・各Protocol)は、いずれも既定値付きフィールド
追加による後方互換な拡張、またはCEOが明示的に指示した契約変更
(RequirementExtractorProtocolの3引数への復元)である。
