# Known Limitations(forge_ai v0.1)

事実と推測を分離するため、確認済みの制限を明記する。

## 1. MockProviderの日本語トークナイズは単純な空白区切り

`provider/mock_provider.py`の`_handle_meaning`は、テキストを空白で分割する
だけの単純な実装である。日本語は分かち書きされない言語のため、
「買い物リストを記録したい」のような文は1トークンとして扱われる
(実際に確認済み。`tests/test_provider_and_prompt.py`は、この制限を
回避できる英語混じりの入力でテストしている)。

**影響範囲**: MeaningExtractor以降の全段階(Intent/Planner/Compiler)は
MockProviderが返すトークンに依存するため、分かち書きされていない
日本語文をそのまま渡すと、Compilerが生成するchecklist項目が
「文全体」1件になることがある(クラッシュはしない。空チェックリストにも
ならない。単に意味的な分解ができないだけ)。

**対応方針**: 実LLM Provider接続後に解消される見込み(実LLMは形態素解析を
必要とせず、文全体から直接構造化データを抽出できるため)。それまでは
既知の制限として扱う。

## 2. Compilerは常にChecklistテンプレート形状を出力する

`core/compiler.py`は、Application Planの内容によらず、常に
「checklist + 追加用text_field/button」という1つの構造パターンへ
コンパイルする(Forge Language側で最も実績のあるTemplateと同じ形)。

**影響範囲**: Hospital・Attendance等、必ずしもchecklistが最適とは
限らないDomainでも、同じ構造になる。

**対応方針**: 今回のスコープは「世界理解〜設計まで」であり、Compilerの
高度化(Domain・Intentに応じて異なるForge Templateを選択する等)は
次フェーズの拡張点として位置づける(意図的な今回のスコープ限定であり、
見落としではない)。

## 3. RepairEngineの決定的修正パターンは2種類のみ

`repair/repair_engine.py`の`_try_fix`は、`missing_app_title`と
`empty_checklist_state`という2つの既知カテゴリのみを決定的に修正する。
それ以外のカテゴリは(クラッシュはしないが)未修正のまま
`remaining_issues`として返る。

**対応方針**: 本物のValidator(Backend側)が実際にどんな`category`の
問題を報告するかが分かってから、対応パターンを拡充する
(今回はBackendのValidatorへ依存しない設計にしているため、
issue categoryの語彙はforge_ai/独自の暫定的なものである)。

## 4. QualityEngineの重み付けは単純平均

`quality/quality_engine.py`の`QualityScore.overall`は6軸の単純平均。
軸ごとの重要度に差がある可能性が高いが(例: Runtime Safetyは
Simplicityより重大な問題であるはず)、今回は単純化した。

**対応方針**: `overall`の算出方法だけを差し替えられる設計にしてある
(`QualityScore.overall`プロパティ1箇所の変更で済む)。実際の生成結果が
蓄積されてから、重み付けを検討する。

## 5. Compilerが生成するIRはForge Language v1.0のみを対象とする

Forge Language v1.1/v1.2(heading/checkbox/card/list/divider/form、
Action拡張、Validation)は、`shared/schemas/`側に既に存在するが、
forge_ai/のCompilerは現時点でv1.0語彙(text/text_field/button/column/row/
checklist)のみを使う。

**対応方針**: forge_ai/はRuntime/Backendを一切importしない設計のため、
v1.1/v1.2の語彙を「知る」には、Compiler内に手動でスキーマ情報を
同期させる必要がある。今回のスコープ(世界理解〜設計まで)では、
最も枯れたv1.0だけを対象にすることで、確実性を優先した。
