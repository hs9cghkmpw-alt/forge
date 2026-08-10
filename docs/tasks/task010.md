# Task010 — FORGE-RUNTIME-003: Infinite Width Button Constraint Fix

## 依頼内容
- CEO実機のスタックトレース(`BoxConstraints forces an infinite width`、
  `ElevatedButton ← Row ← Column ← ... ← Scaffold`)により確定した根本原因を
  修正する。`Size.fromHeight`が幅Infinityを意味する点への対処。
- Button自身が常に無限幅を要求しないよう、stretch責務を親レイアウトへ分離する。
- Forge Language上にfullWidth等のprop有無を確認し、無ければLanguage追加せず
  安全なデフォルトへ修正する。
- `frontend/lib/`全体でInfinity関連の他の危険箇所を監査する。
- Button単体/Column内/Row内/ScrollView内/複合構造/複数個/800x600/狭いviewport、
  の8シナリオで回帰テストを追加する。
- 既存E2Eテスト(`kids_checklist_generation_flow_test.dart`)を削除・弱体化せず、
  修正後に通る前提で静的確認する。
- FORGE-RUNTIME-002での3修正(mainAxisSize/Key/IconButton化)が実際には
  根本原因ではなかったことを整理する(無条件に元へ戻す必要はない)。

## 行った変更
- `core/theme/forge_theme.dart`: `elevatedButtonTheme.minimumSize`を
  `Size.fromHeight(56)`(=`Size(double.infinity, 56)`)から`Size(0, 56)`へ
  修正。高さ56(≥48)は維持、幅の無限指定のみ除去。
- `frontend/lib/`全体を`Size.fromHeight(`・`double.infinity`・`minWidth`/
  `maxWidth`・`fixedSize`/`minimumSize`/`maximumSize`で検索し、該当は
  `forge_theme.dart`の1箇所のみだったことを確認した。
- `features/app_generation/presentation/screens/home_screen.dart`: 送信
  ボタンを`SizedBox(width: double.infinity, child: ElevatedButton(...))`で
  包み、テーマ側で失った全幅表示を呼び出し側で明示的に復元した。
  `confirm_screen.dart`は元々`crossAxisAlignment: stretch`を使っており、
  コード変更は不要だった。
- `test/json_ui/button_layout_regression_test.dart`新設。8シナリオ、
  すべて`ForgeTheme.theme`を適用した状態で検証。viewport操作は
  非推奨API(`window.physicalSizeTestValue`)ではなく現行の
  `tester.view.physicalSize`を使用。
- `docs/DECISIONS.md` D29(根本原因の技術的説明: RenderFlexの主軸/交差軸の
  違いにより、Column上のCross-axis(有限loose制約)ではクランプされて
  安全に動いていたが、Row上のMain-axis(unbounded制約)では破綻していた)、
  D30(全幅化責務の移動)を追加。D26に、RUNTIME-002の3修正が実際には
  原因ではなかったことを追記(削除・改変はせず追記のみ)。

## 変更理由
CEOから提供された完全なスタックトレースにより、初めて根本原因を確定できた。
「事実と推測を厳密に分離する」に従い、FORGE-RUNTIME-002時点の推測
(3箇所の対処療法的修正)を「原因修正」と偽らず、正直に「原因ではなかった」と
訂正した上で、それらの改善自体は妥当なものとして維持する、という整理を行った。
