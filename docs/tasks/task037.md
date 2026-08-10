# Task037 — FORGE-MILESTONE-007 Phase 1.1: 契約精度・品質評価・UX改善

## 依頼内容
CEOがM007 Phase 1の実物監査(139/265件全合格を確認済み)を行い、
条件付き承認とした上で、7点の修正を求めた。新しいDomainや大規模機能を
追加せず、既存の最小実装の契約精度・品質評価・ユーザー体験を改善する
ことに限定するよう指示された。

1. 実装位置づけの訂正(Blueprint v1.3ではなくM007 Phase 1 Minimal
   Cognitive Sliceとして明示)。
2. Provider契約の回復(`run_cognitive_pipeline()`へ`provider`を
   正式な引数として追加)。
3. Template Selectionの同点解決を辞書登録順ではなく決定的な規則にする。
4. 「エラーにせず何もしない」Validation既定の廃止、アプリらしい
   UXへの改善。
5. Critic/Qualityのscore=1.00がアプリ全体の品質1.00を意味しないよう
   誤解防止する。
6. 単一のDomainClassification.confidenceだけで確信度を表現せず、
   Intent抽出confidence・Domain coverage・Score marginを分離する。
7. 上記修正後のテスト・報告。

## 行ったこと
- `run_cognitive_pipeline()`へ`provider: AIProvider | None = None`を
  追加し、`Compiler`へ実際に注入されることを3件のテストで確認した。
- `TemplateSelectorProtocol.select_final()`へ`preliminary_candidates`
  引数を追加し、Preliminary候補優先→Dominant action一致数→Data
  lifecycle一致数→genericという4段階の決定的tie-breakを実装した。
  「買い物リストを作りたい」がchecklist/trackerの同点をPreliminary
  候補で解決することをテストで検証した。
- Validation要件を1件から5件へ分割し、空入力時の無視(既存M005教訓)と
  必須項目未達成時の理由表示・入力保持・修正方法明示・フォーカス
  移動を区別した。
- `CriticReport`へ`implemented_checks_score`・`coverage_ratio`・
  `evaluated_axes`・`unevaluated_axes`を追加し、未割当のmandatory
  要件・Privacy要件をrelease_readyのblocking条件にした。単一画面の
  navigation不要と複数画面でのnavigation_edges欠落を区別する
  navigation_coherence軸を新設した。この過程で、「data」カテゴリの
  要件が常に未割当扱いになっていた実バグを発見・修正した。
- `intent.confidence`・`classification.domain_coverage`・
  `classification.score_margin`を明示的に組み合わせる
  `_should_escalate_for_low_confidence()`を実装し、5件のテストで
  各組み合わせを検証した。
- 「Blueprint v1.3の実装」という表現を「M007 Phase 1 Minimal
  Cognitive Slice」へ統一し、Meaning Model未実装・実装済み13段階を
  明記した。
- Forge AI全テスト(156件、既存139件維持+新規17件)・Backend全テスト
  (265件、無影響)を実行し、CEO指定6例全てが引き続き成功することを
  確認した。

## 変更理由
CEOの明示的な指摘に基づく。実装中に発見した「data」カテゴリ要件の
割当漏れバグは、指摘5(mandatory未割当のblocking)を正しく実装する
ために必須の修正だった(修正しなければ6例全てが誤って
NeedsConfirmationになってしまうため)。
