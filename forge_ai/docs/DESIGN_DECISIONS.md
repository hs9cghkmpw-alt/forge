# Design Decisions(forge_ai v0.1)

キックオフ指示書14章「設計変更が必要な場合は、変更理由・代替案・影響範囲を
記録してから実施すること」に対応する記録。実装前に固定した設計判断と、
実装中に発見し記録した判断の両方を含む。

## D1. `set_state`/`toggle_state`等のForge Runtime語彙とは独立させた

forge_ai/は、既存のFlutter Runtime(FORGE-MILESTONE-003で拡張したAction
語彙: set_state/toggle_state/reset_state/submit_form/composite等)を
一切importしない。Compilerが生成するIRは、より枯れたv1.0語彙
(navigate/go_back/set_value/add_item)のみを使う。

**理由**: 今回のキックオフ指示書は「Flutter側のRuntimeは変更禁止」
「forge_ai/のみ」と明確にスコープを区切っている。Runtime側の最新語彙を
知るには、Runtime側のコードまたはスキーマを直接参照する必要があり、
それは「Runtime依存0件」という完了条件に反する。

**代替案として検討したが採用しなかったもの**: `shared/schemas/
ui_schema.v1.2.json`をforge_ai/内へ複製する案。しかし複製すると
「手動同期が必要な二重管理」がforge_ai/内に生まれてしまい、
「forge_ai/のみ」というスコープの純粋性が保てないため見送った。

**影響範囲**: `docs/KNOWN_LIMITATIONS.md` 5章に記録。

## D2. Compilerは決定的なPython実装を主とし、Providerはタイトル判断のみに使う

`core/compiler.py`のWidget構造組み立ては、Providerを呼ばない決定的な
Python実装にした(Providerは`app_title`の判断にのみ使う)。

**理由**: 画面構造の組み立て自体をProvider(将来的にはLLM)任せにすると、
MockProviderでのテストが「Mockが何を返すか」に強く依存し、
再現性・テスト容易性が下がる。Forge Widget/Action/State語彙という
決まった文法へ変換する部分は、むしろ決定的であるべきという判断
(禁止事項6章「JSON直接編集」の回避にも寄与する: AIが自由な構造を
決めるのではなく、決まった文法の中でのみ変数(タイトル・項目名)を
決める)。

**代替案**: Provider側にIR全体をJSON文字列で生成させ、パースする案。
「LLMに不安定なJSON形式を学習・生成させるべきではない」という
キックオフ指示書2章の理由に直接反するため採用しなかった。

## D3. RepairEngineの`_try_fix`は既知2パターンのみ、それ以外はそのまま返す

**理由**: 本物のValidator(Backend側)がまだ接続されていない現段階では、
実際にどんな`category`の問題が発生するか経験的に分かっていない。
無理に多くのパターンを先回りして実装すると「将来使うかもしれない機能の
先行実装」(禁止事項11章、Forge共通指示書23章と同じ原則)になる。

**影響範囲**: `docs/KNOWN_LIMITATIONS.md` 3章に記録。

## D4. Pipeline(`core/pipeline.py`)はRepairEngineを含めなかった

`run_pipeline()`はDomain解決からQuality評価までを実行するが、
RepairEngineの呼び出しは含めていない。

**理由**: RepairEngineは「どの問題を直すか」という`RepairIssue`の
リストを外部から与えられて初めて動作する。Validator接続前の現段階では、
この`issues`をパイプライン内部で自動生成する手段が無い(forge_ai/は
Validatorを持たない)。呼び出し側が明示的に`RepairEngine.repair()`を
呼ぶ設計とした。

**影響範囲**: Runtime/Validator接続後、`issues`の生成元
(Backend Validatorの出力をforge_ai/の`RepairIssue`へ変換するアダプタ)を
別途実装する必要がある。次フェーズの拡張点として`README.md`に記録。

## D5. `__init__.py`を全サブパッケージへ追加した(実装中に発見・追記)

**発見の経緯**: 当初`__init__.py`無し(暗黙的namespace package)で実装した
ところ、`python -m unittest discover -s forge_ai/tests -t forge_ai`のような
一部の起動方法で`ImportError: Start directory is not importable`が
発生することを実際に確認した。

**変更内容**: `forge_ai/`と全サブディレクトリへ空の`__init__.py`を追加した。

**影響範囲**: 追加のみ(既存コードのimport文は変更不要、名前空間
パッケージから明示的パッケージへ変わるだけで後方互換)。追加後、
複数の起動方法(`-t .`あり/なし、`forge_ai/`内から実行等)すべてで
80件のテストが正しく実行できることを実際に確認した。実装中に発見した
軽微な構造変更のため、この文書に記録した上で実施した
(指示書14章の手続きに従った)。

## D6. FORGE-MILESTONE-004として正式に提出する(既存実装の検証・強化として)

**経緯**: 「FORGE-MILESTONE-004を開始してください。目的はForge AI v0.1
（Cognitive Engine）の基盤構築です。LLM非依存・Mock Provider前提で、
Domain Model・World Model・Meaning Model・Intent Model・Plannerを実装
してください」という依頼を受けた。

**事実確認**: この依頼を受けた時点で、`forge_ai/`にはすでにDomain Model・
World Model・Meaning Model・Intent Model・Planner(+Compiler・Repair
Engine・Quality Engine・Provider Interface・Prompt Builder・Contracts)
が実装済みで、80件のテストが全件合格する状態だった(以前の
「FORGE PROJECT — AI実装チーム キックオフ指示書」に基づく実装)。
LLM非依存であることも、全ソースファイルのimport文を再確認して
検証済み(標準ライブラリとforge_ai内部モジュール以外への依存が無い)。

**今回行ったこと**: ゼロから再実装するのではなく、既存実装を
「FORGE-MILESTONE-004の正式な提出物」として検証・強化する形で対応した。
具体的には、型ヒント・Docstringが100%であることの再確認(`ast`による
静的解析)、全80テストの再実行による合格確認、`py_compile`による
構文エラー0件の再確認を行った。新規に発見した実装ギャップは無かった。

**他のNative AI関連コードとの関係(訂正あり)**: `backend/app/ai/runtime/`
内の一部ファイル(intent_parser.py・native_ai_runtime.py・
template_engine.py・template_selector.py)は、`docs/reports/
FORGE-MILESTONE-004-report.md`(2026-07-13付、「Native AI Phase-1
（Intent Engine）」)という正規の報告書、および`docs/DECISIONS.md`
D50〜D55・`TECH_DEBT.md` TD20〜TD22という正規の記録形式で、既に
文書化されていることを確認した(前回のFORGE-MILESTONE-003.1レポートで
「由来を追跡できない」と報告したのは不正確だったため、ここで訂正する)。

`backend/app/ai/native/`(intent_recognizer.py等)の由来は依然として
確認できていない。

`forge_ai/`と「Native AI Phase-1」(`backend/app/ai/runtime/`)は、
概念的に重複する部分(Intent/Planner)を持つ別の実装として並存している。
どちらも「FORGE-MILESTONE-004」という同じ名前で呼ばれているが、
内容は異なる。統合方針は今回も決定しておらず、CEO判断を仰ぐ事項として
`FORGE-MILESTONE-004-report.md`(今回分)に記録した。

## D7. 「FORGE-MILESTONE-004」の番号重複をArchitecture Freezeで解消した

D6で報告した「forge_ai/と"Native AI Phase-1"がどちらも
FORGE-MILESTONE-004と呼ばれている」という問題は、CEOレビューを受けて
`docs/spec/FORGE_AI_ARCHITECTURE_V1.md`(Architecture Decision Record)で
正式に解消した。

- **M004 = forge_ai/(本パッケージ)のみ**、と確定した。
- 旧「Native AI Phase-1」は M005(`backend/app/ai/runtime/`)として
  正式に読み替える。
- `backend/app/ai/native/`はM006以降・Experimental扱いとし、
  CEO承認なしに変更しないことを確定した。

これにより、forge_ai/は今後「M004: Forge AI Core」という、他と重複しない
一意なマイルストーン番号を持つ。

## D8. `_DOMAIN_TO_PRELIMINARY`の完全性を、テストだけでなくモジュール
読み込み時にも自己検証する(2026-07-21)

**背景**: CEOから、`household_budget`が`_DOMAIN_TO_PRELIMINARY`
(`forge_ai/core/planning/template_selector.py`)へ登録されておらず、
`preliminary_final_mismatch_exhausted`で確認要求に落ち続けるという
不具合の報告を受けた。調査の結果、この特定の不具合は既にFORGE v0.3
時点で修正済みであることが判明した(`docs/tasks/task041.md`・
`FORGE-TEMPLATE-SELECTOR-AUDIT-report.md`に詳細)。ただし、CEOの
「同種の再発防止」という指示は正当であり、以下を追加した。

- `DomainCategory`の全`.value`が`_DOMAIN_TO_PRELIMINARY`に登録
  されていることを検証する、単一の判定関数
  `_missing_domain_preliminary_entries()`を新設した。
- **この関数を、モジュールが`import`された瞬間に呼び出し、欠落が
  あれば`RuntimeError`で即座に失敗させる**(テストの実行有無に
  関わらず、実際にforge_aiパイプラインが動く経路・テスト実行経路の
  いずれでも必ず通る)。「新Domainを追加したのに、この辞書への
  追記だけ忘れる」というクラスの不具合を、テストの存在を覚えている
  ことに依存せず、構造的に防ぐ。
- 同じ判定関数を、`forge_ai/tests/test_planning_and_critic.py`の
  テストからも呼ぶことで、検出ロジックを重複させない(Single
  Source of Truth)。

**あわせて対応した関連事項**:
- `forge_ai/tests/`(356件、D9時点で360件)がCI(`.github/workflows/
  ci.yml`)から一度も実行されていなかったことを発見し、独立したCI job
  (`forge-ai-test`)として新設した(既存の`backend-lint-test`は
  `working-directory: backend`から`pytest`を実行するため、兄弟
  ディレクトリである`forge_ai/tests/`を探索できていなかった)。
- `differs_from_preliminary`が真偽値であり、ADR-008が本来意図した
  「著しく異なる」という程度を表現できていないという設計上の
  ギャップを発見し、`docs/adr/ADR-013-template-selection-mismatch-
  severity.md`として設計改善案(未実装)を記録した。

## D9. D8の完全性チェックを`AssertionError`から`RuntimeError`へ修正
した(2026-07-21、CEO指摘)

D8で導入したモジュールimport時の完全性チェックは、当初
`raise AssertionError(...)`という実装だった。CEOから、「Pythonの
`assert`は`python -O`実行時に除去されるため、Runtimeの不変条件
チェックには使うべきではない」という指摘を受けた。

**事実確認(重要)**: 実際に`python -O`で検証したところ、この実装は
**`-O`によって無効化されなかった**。理由は、この実装が`assert`文
そのもの(`assert 条件`という構文)ではなく、`if missing: raise
AssertionError(...)`という**明示的な`raise`文**だったため。
`python -O`が除去するのはあくまで`assert`文・`if __debug__:`
ブロックのみであり、たとえ例外の**型**が`AssertionError`であっても、
`raise`によって明示的に送出する分には`-O`の影響を受けない。

とはいえ、`AssertionError`という型名自体が「デバッグ時のみの検査」
という印象を与え、将来この部分を本当の`assert`文へ書き換えて
しまうリスクがあるというCEOの懸念は妥当と判断し、`RuntimeError`へ
変更した。あわせて以下を行った。

- 送出ロジックを`_raise_if_domain_preliminary_incomplete(missing)`
  という独立した関数へ切り出し、この関数を直接呼ぶユニットテスト
  (`RuntimeError`が送出されること・不足Domain名が全てメッセージに
  含まれること・空集合では何も送出しないこと)を追加した。
- `_extra_domain_preliminary_entries()`という、逆方向(辞書にはある
  がDomainCategoryには無いキー)を検出する関数も新設した。**この
  逆方向は、import時のfail-fastには含めないと明文化した**——余分な
  キーは`.get()`から参照されないだけで実害が無く、Domainの
  rename・削除に伴う一時的な取り残しである可能性が高いため。ただし
  タイポ発見の手がかりにはなるため、テストレベルで継続的に検査
  する。
- 実際に`python -O`でモジュール全体のimport・完全性チェックの
  送出ロジックの両方を検証し、`-O`の有無に関わらず同じ結果になる
  ことを確認した(forge_ai全360件のテストスイートを`-O`有り・
  無し両方で実行し、結果が一致することも確認済み)。

## D10. ADR-007実装第1段階(Task042-1): ConfidenceRecord・
overall_confidenceを観測専用として導入した(2026-07-21)

CEO承認済みの3段階計画(`docs/tasks/task042.md`)のうち、最もリスクの
低い第1段階のみを実装した。

- `ConfidenceRecord{value, basis}`・`OverallConfidence`
  (`intent_confidence`・`domain_confidence`必須、`entity_
  confidence`・`planning_confidence`・`template_confidence`は
  将来拡張用に任意で`None`許容)を新設した。
- `.value`(overall_confidence)は、現時点で値が存在する要素だけの
  単純平均とした(`available_components`というプロパティで、将来
  entity/planning/template confidenceが実装され次第、自動的に
  平均へ加わる設計)。
- **既存の`_should_escalate_for_low_confidence()`・`_is_low_risk_
  reversible()`は1行も変更していない。** 新しい`overall_confidence`
  は`DecisionTrace`へ観測記録するだけであり、どの`if`分岐にも
  使われていないことを、呼び出し箇所を直接確認して検証した。
- **発見した問題(実装中)**: 新しいDecisionTraceステージの追加により、
  `test_cognitive_pipeline_complex_golden.py`のgolden test 6件が、
  `decision_trace_stages`リストの不一致で失敗する状態になっていた。
  他の全フィールドが変わっていないことを個別に確認した上で、
  golden fileを「意図した変更」として更新した(このテスト自体が
  そのための更新手順をエラーメッセージに明記していた)。

**CEOからの明示的な方針(Task042-2への申し送り)**: ADR-007が提案する
0.5/0.8という単一閾値へ`_should_escalate_for_low_confidence()`を
単純に置き換えるのではなく、既存の3信号モデル(intent confidence・
domain coverage・score margin)を内部要素として残しつつ、
`overall_confidence`と比較実験できる状態を作ることを優先する。
`OverallConfidence.available_components`という設計(個別の信号を
早期に単一floatへ潰さない)は、まさにこの将来の比較実験を見据えた
ものである。

## D11. Task042-2 Phase B: ShadowJudgmentによる現行モデル・overall_
confidenceモデルの比較(観測専用)(2026-07-21)

D10の続き。CEO承認済みの設計(`FORGE-TASK042-2-DESIGN-PROPOSAL.md`)
に基づき、以下を実装した。

- `_should_escalate_for_low_confidence()`(現行モデル)を、
  `confidence.compute_legacy_escalation_reasons()`という共有関数を
  呼ぶだけの薄いラッパーへリファクタリングした。**重要**: 切り出した
  関数は元の実装と一字一句同じ4条件・同じ閾値を評価するため、
  `bool(...)`の結果は完全に同一である。これにより、現行モデル本体と
  Shadow比較(`compute_shadow_judgment()`)が、判定ロジックを
  重複させずに同じ実装を参照する。
- `ThresholdsUsed`(現行・Shadow双方の閾値を構造化データとして保持、
  コード中に埋め込むだけにしない)・`ShadowJudgment`(現行モデルの
  判定・Shadowモデルの判定・4分類の`comparison_category`・
  6分類の`risk_classification`等を保持)を新設した。
- `DecisionTrace`へ`shadow_judgment`フィールドを追加し、既存の
  `overall_confidence_observation`ステージへ記録するようにした
  (新しいステージは追加していない、Task042-1で経験したGolden Test
  破損を今回は回避できた)。
- Golden Test全42件を実際にPipelineへ通して比較レポートを生成した
  結果、**一致率100%(不一致0件)**。36件が`both_continue`、
  6件が`both_escalate`。単独の信号だけが低い(`*_only_low`)ケースは
  今回のcorpusに1件も無かった(`multiple_signals_low`が6件、
  `medium_band`が7件)。

**この結果の解釈(重要な注記)**: 一致率100%は心強い結果だが、
42件という少ないサンプルであり、`score_margin`が新モデルの計算に
反映されていないという既知の構造的な乖離(D10参照)が、たまたま
今回のcorpusでは顕在化しなかっただけの可能性がある。Phase Cへ
進む前に、より多様な入力(特に僅差判定が効くはずの入力)での追加
検証が望ましい。

**訂正(2026-07-22)**: 上記の初回比較には、`_all_golden_prompts()`の
タプル順序不一致バグがあり、複雑入力6件は実際の日本語入力ではなく
ケース名文字列で検証していたことが判明した(詳細は
`docs/tasks/task042.md`追記3参照)。修正後、42件全てが`high_
confidence`または`medium_band`に分類され、低confidence領域
(`*_only_low`・`multiple_signals_low`)は現在のGolden Test corpusに
1件も存在しないことが分かった。「一致率100%」という結果自体は
変わらないが、**この結果が持つ情報量は、初回想定より小さい**
(低confidence領域を一切検証できていないため)。境界値テストが、
この領域をカバーする唯一の検証手段になっている。
