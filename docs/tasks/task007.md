# Task007 — FORGE-MERGE-005: Flutter Analyze Zero-Issue Fix

## 依頼内容
- CEO実機で`flutter test`が7/7 PASS、`flutter analyze`がError 0・Warning 3件
  (`MaterialPageRoute`の型引数推論不能)であることが判明。この3件を最小変更で修正する。
- Repository全体で型引数なしの`MaterialPageRoute`が他に無いか監査する。
- 修正が画面遷移・UI・状態管理に影響しないことを説明する。
- Warning抑制(`ignore`コメント等)を使わず、実際の指摘に対応する。

## 行った変更
- `home_screen.dart`・`confirm_screen.dart`・`forge_renderer.dart`の
  `MaterialPageRoute`3箇所に`<void>`を付与。各箇所で戻り値が実際に未使用
  であることをコードを読んで個別に確認した上で適用した。
- `grep -rn "MaterialPageRoute"`でRepository全体を検索し、3件以外に
  存在しないことを確認した。
- `TECH_DEBT.md`にTD9(Navigator遷移がテストで検証されていない)を追記した。
  今回の回帰影響確認の過程で見つけた、既存テストスイートの正直な限界。

## 変更理由
指示書の「今回の最終合格判定は、CEO環境で`No issues found!`・
`All tests passed!`が確認できた時点とする」に従い、Warning抑制ではなく
実際の型注釈追加で対応した。3箇所とも機械的に同じ`<void>`という結論に
なったが、それぞれ個別にコードを読んで確認した結果であり、確認を省略して
一括置換したわけではないことをレポートで明記した。
