# Task041 — Template Selector監査・CI統合・完全性チェック・設計改善提案

**Status: 実装済み・CI実行待ち**(2026-07-21時点。`forge-ai-test`
CI jobが実際にGitHub Actions上で成功したことを確認するまで、この
Taskを完了扱いにしない。CEO指示による)。

## 依頼内容

CEOから、`household_budget`が`_DOMAIN_TO_PRELIMINARY`
(`forge_ai/core/planning/template_selector.py`)へ登録されておらず、
`preliminary_final_mismatch_exhausted`で確認要求に落ち続けるという
不具合の報告と、修正済みコードの提示があった。これを受けて、以下を
依頼された。

1. `Domain`の全カテゴリを`_DOMAIN_TO_PRELIMINARY`と突き合わせ、
   未登録が無いか監査する。
2. 未登録があれば、Intent/Requirement/ApplicationPlan/Final
   Selectorの評価基準と整合する妥当な値を追加する。
3. `household_budget`の回帰テストを追加する。
4. 「Preliminary/Final不一致は必ず確認要求へ繋がる」設計自体も
   見直す(ただし既存仕様・テストを無断で変更せず、最小変更案と
   堅牢化案を分けて提示する)。

調査の結果、報告された不具合はCEOの手元のワークツリーが古い状態
だったことに起因し、本セッションのコードベースでは既にFORGE v0.3
時点で修正済みであることが判明した(`FORGE-TEMPLATE-SELECTOR-
AUDIT-report.md`参照)。CEOはこの説明に納得した上で、続けて以下を
依頼した。

1. 追加した回帰テスト・golden testをCIへ組み込む。
2. `DomainCategory`と`_DOMAIN_TO_PRELIMINARY`の対応漏れを、辞書の
   手動管理に依存しない形で検出する仕組みを追加する。
3. 「`differs_from_preliminary`が真偽値であり、程度を表現できない」
   という設計ギャップについて、別Issueとして設計改善案(提案のみ、
   Runtime変更なし)をまとめる。
4. 今回の内容をCHANGELOGと開発者ドキュメントへ反映する。

## 行ったこと

- `forge_ai/core/domain_model.py`の`DomainCategory`全14カテゴリを
  監査し、`_DOMAIN_TO_PRELIMINARY`に未登録のものが無いことを確認
  した。`test_v03_domain_inference_golden.py`の36プロンプト全件を
  実際にPipelineへ通し、1件もPreliminary/Final不一致を起こさず
  Successへ到達することも確認した。
- `test_planning_and_critic.py`の`TestTemplateSelector`へ、
  `household_budget`固有の回帰テスト4件と、全Domain登録監査
  テスト1件を追加した。
- `template_selector.py`へ、`_missing_domain_preliminary_entries()`
  という単一の判定関数を新設し、**モジュール読み込み時に自動的に
  呼び出して**、欠落があれば例外(当初`AssertionError`、後にCEO指摘
  により`RuntimeError`へ修正。追記参照)で即座に失敗する自己検証を
  追加した(テストの実行有無に依存しない検出)。既存のテストもこの
  関数を呼ぶよう更新し、判定ロジックを重複させないようにした。
- `.github/workflows/ci.yml`に`forge-ai-test`というジョブを新設
  した。既存の`backend-lint-test`が`working-directory: backend`から
  `pytest`を実行するため、兄弟ディレクトリの`forge_ai/tests/`
  (360件、本Task完了時点)が一度もCIで実行されていなかったことを
  発見し、修正した。
- `docs/adr/ADR-013-template-selection-mismatch-severity.md`を
  新設し、`differs_from_preliminary`を真偽値から「不一致の深刻度」
  を表現できる形へ改善する提案(Context/Decision/Alternatives/
  Consequences/Migration/Revisit Conditions)をまとめた。
  Status: Proposed(未実装)とし、Runtime挙動は変更していない。
- `forge_ai/docs/DESIGN_DECISIONS.md`へD8として、今回の変更内容の
  要約を追記した。
- `CHANGELOG.md`へTask041のエントリを追記した(本ファイル)。

## 変更理由

CEOの明示的な依頼に基づく。特に、CI統合(項目1)は「テストを追加
しただけで実行されていない」という潜在的なリスクを解消するため
必須であり、完全性チェック(項目2)は「テストファイルの存在を
覚えておく」という人間の記憶に依存しない、より構造的な安全網を
求める指示に応えるものだった。設計改善提案(項目3)は、CEOが明示的に
「Runtimeの挙動変更は行わず、改善案のみ」と指定したため、ADRという
形で文書化するに留めた。

## 既存挙動への影響

`template_selector.py`への変更(完全性チェックの追加)は、現時点で
`_DOMAIN_TO_PRELIMINARY`に欠落が無いため、実際には何も失敗させない
(既存の動作に影響なし)。CIワークフローへの追加は新しいジョブの
追加のみで、既存の`backend-lint-test`・`frontend-analyze-test`は
無変更。ADR-013はドキュメントのみで、Runtimeコードへの変更を
一切含まない。

forge_ai全356件(この時点、後の追記で360件に増加)・backend全400件の
テストが引き続き合格することを確認済み。

## 追記(2026-07-21、同日中の修正)

CEOから、完全性チェックの実装(`raise AssertionError(...)`)について
「Pythonの`assert`は`python -O`実行時に除去されるため、Runtimeの
不変条件チェックとして弱い」という指摘を受けた。

調査の結果、この実装は`assert`文そのものではなく明示的な`raise`文
だったため、実際には`-O`で無効化されないことを確認したが(forge_ai/
docs/DESIGN_DECISIONS.md D9参照)、型名が誤解を招くというCEOの懸念は
妥当と判断し、`RuntimeError`へ変更した。あわせて、送出ロジックを
独立関数(`_raise_if_domain_preliminary_incomplete`)へ切り出し、直接
呼び出すユニットテストを追加、逆方向(余分な未知キー)の検出関数
(`_extra_domain_preliminary_entries`)も新設した。詳細は
`FORGE-TEMPLATE-SELECTOR-CI-HARDENING-PATCH1-report.md`参照。

forge_ai全360件のテストを`python -O`有り・無しの両方で実行し、
結果が一致することを確認済み。backend全400件も無変更のまま合格。
