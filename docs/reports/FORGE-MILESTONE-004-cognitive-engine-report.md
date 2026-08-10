# FORGE-MILESTONE-004 実施レポート — Forge AI v0.1 (Cognitive Engine) 正式提出

**Ref:** FORGE-MILESTONE-004　**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-14

---

## 0. 最初にお伝えすべきこと(重要)

作業を始める前に確認したところ、2点の事実が分かった。

**事実1**: 依頼内容(Domain Model・World Model・Meaning Model・
Intent Model・Planner、LLM非依存、Mock Provider前提)と完全に一致する
実装が、`forge_ai/`として既に存在していた(80件のテストが全件合格)。
これは以前の「FORGE PROJECT — AI実装チーム キックオフ指示書」に
基づいて実装されたものである。

**事実2**: `docs/reports/FORGE-MILESTONE-004-report.md`という、
**同じ「FORGE-MILESTONE-004」という名前で、しかし異なる内容
(「Native AI Phase-1（Intent Engine）」、2026-07-13付)の報告書が
既に存在していた。** この報告書は`backend/app/ai/runtime/`を
IntentParser/TemplateEngine/TemplateSelector/NativeAIRuntime bundle等で
拡張する内容であり、`forge_ai/`(Domain/World/Meaning/Intent/Planner)
とは別の実装だった。`docs/DECISIONS.md` D50〜D55・`TECH_DEBT.md`
TD20〜TD22も、この「Native AI Phase-1」に対応する内容として既に
記録されていた。

**つまり「FORGE-MILESTONE-004」という名前が、2つの異なる内容
(a. Native AI Phase-1 = backend/app/ai/runtime/の拡張、
b. 今回の依頼 = forge_ai/相当のDomain/World/Meaning/Intent/Planner)
に対して使われている状態**だと理解した。前回(FORGE-MILESTONE-003.1)の
時点では、この経緯を「由来不明」として報告していたが、今回
`docs/reports/FORGE-MILESTONE-004-report.md`を実際に読み直し、
DECISIONS.md D50〜D55・TECH_DEBT.md TD20〜TD22という、正規の記録形式で
既に文書化されていたことを確認できた。前回の「由来を追跡できない」
という報告は不正確だったため、ここで訂正する。

**今回取った対応**: 今回の依頼文言(Domain Model・World Model・
Meaning Model・Intent Model・Planner)と一致するのは`forge_ai/`である
ため、`forge_ai/`をゼロから再実装するのではなく、検証・強化した上で
今回の依頼の正式提出物として採用する。「Native AI Phase-1」
(backend/app/ai/runtime/拡張)は別の実装として現状のまま残す
(重複の解消は行わない)。この判断でよいか、あるいは2つの
「FORGE-MILESTONE-004」をどう整理すべきかについては、7章でご確認
いただきたい。

---

## 1. 依頼内容とforge_ai/の対応関係

| 依頼内容 | forge_ai/での実装 |
|---|---|
| Domain Model | `core/domain_model.py`(`Domain`/`DomainCategory`/`DomainRegistry`) |
| World Model | `core/world_model.py`(`Actor`/`WorldObject`/`Relationship`/`Rule`/`World`) |
| Meaning Model | `core/meaning_model.py`(`ExtractedMeaning`/`MeaningExtractor`) |
| Intent Model | `core/intent_model.py`(`Intent`/`IntentBuilder`) |
| Planner | `core/planner.py`(`ApplicationPlan`/`ScreenPlan`/`Planner`) |
| LLM非依存 | `provider/provider_interface.py`(`AIProvider` Protocol)のみに依存 |
| Mock Provider前提 | `provider/mock_provider.py`(決定的、実LLM非呼び出し) |
| Runtime/Flutter/Backend API/実LLM接続は対象外 | 該当する依存が無いことを再確認済み(2章) |

依頼にない範囲として、`core/compiler.py`・`repair/repair_engine.py`・
`quality/quality_engine.py`・`prompt/prompt_builder.py`・
`contracts/interfaces.py`も既に実装されている(以前の、より広い
スコープの依頼に基づくもの)。今回はこれらの削除・縮小はしていない。

---

## 2. 今回実施した検証(実行結果、事実)

```
$ cd forge && python3 -m unittest discover -s forge_ai/tests -p "test_*.py"
Ran 80 tests in 0.046s
OK
```

```
$ find forge_ai -name "*.py" -exec python3 -m py_compile {} \;
(構文エラー0件)
```

```
$ <ast静的解析: モジュール/クラス/関数のdocstring・型ヒントを検査>
Source files checked: 20
Docstring/type-hint issues: 0
```

```
$ grep -rn "^import|^from" forge_ai --include="*.py" | grep -v "forge_ai\." | grep -v <stdlib>
(該当なし = forge_ai内部モジュールと標準ライブラリ以外への依存が無いことを確認)
```

いずれも今回実際に実行して確認した結果である。

---

## 3. 「設計を固定してから実装」について

既存実装のため、設計は既に固定・文書化されている。

- `forge_ai/README.md`: 全体のアーキテクチャ・使い方。
- `forge_ai/docs/DESIGN_DECISIONS.md`: D1〜D6(今回D6を追加)。
- `forge_ai/docs/KNOWN_LIMITATIONS.md`: 既知の制限5件。

核となる設計原則: Provider Independence(`AIProvider` Protocolのみに
依存)、Runtime非依存(`Planner`はForge Widget語彙を知らない)、
Prompt Builder経由のみ(文字列連結禁止)、依存方向の一方向性
(`contracts/`は具体実装をimportしない)。

---

## 4. 「Native AI Phase-1」との関係(訂正を含む)

前回のFORGE-MILESTONE-003.1レポートで、`backend/app/ai/runtime/`内の
`intent_parser.py`・`native_ai_runtime.py`・`template_engine.py`・
`template_selector.py`等を「由来を追跡できない」と報告した。

**訂正**: 今回`docs/reports/FORGE-MILESTONE-004-report.md`
(2026-07-13付、「Native AI Phase-1（Intent Engine）」)を実際に読み、
これらのファイルが正規の依頼(PHASE1〜9、16観点のArchitecture Review
込み)に基づいて作成されたものであることを確認した。
`docs/DECISIONS.md` D50〜D55・`TECH_DEBT.md` TD20〜TD22という、
他の正規タスクと同じ形式で記録されている。前回の報告は不正確だった。

**現時点での状態整理**:

| 実装 | 対応する依頼 | 主な内容 |
|---|---|---|
| `forge_ai/` | 「FORGE PROJECT AI実装チーム キックオフ指示書」+ 今回の依頼 | Domain/World/Meaning/Intent/Planner/Compiler/Repair/Quality、独立パッケージ |
| `backend/app/ai/runtime/`の一部 | 2026-07-13付「Native AI Phase-1」 | IntentParser/TemplateEngine/TemplateSelector/NativeAIRuntime、backend統合済みProtocol層 |
| `backend/app/ai/native/` | 由来不明(未確認のまま) | intent_recognizer.py等、ルールベース |

「FORGE-MILESTONE-004」という同じ名前が、上記のうち2つ
(forge_ai/相当の今回の依頼と、Native AI Phase-1)に対して
使われている状態である。

---

## 5. 未解決のまま残す点

- `forge_ai/`と`backend/app/ai/runtime/`(Native AI Phase-1)の統合方針。
  両者は概念的に重複する部分(Intent/Planner)を持つが、今回は
  どちらも変更せず並存させた。
- `backend/app/ai/native/`の由来は依然未確認。
- 「FORGE-MILESTONE-004」という名前が2つの異なる内容を指している
  状態の整理(番号の振り直し、あるいはどちらかを別名称にする等)。

---

## 6. 成果物

1. 本レポート
2. `forge_ai/docs/DESIGN_DECISIONS.md` D6
3. `docs/spec/NATIVE_AI_STATUS_NOTE.md`(更新、訂正を含む)
4. `CHANGELOG.md` Task022
5. `docs/tasks/task022.md`
6. Repository ZIP

新規に追加したコードは無い(既存実装の検証・文書化のみ)。今回
Flutter/Dartのコードは一切変更していない。

---

## 7. CEOへの確認事項

1. 今回の判断(既存の`forge_ai/`を、今回の依頼の正式提出物として
   採用したこと)でよいか。
2. `forge_ai/`と「Native AI Phase-1」(`backend/app/ai/runtime/`)の
   統合方針、および「FORGE-MILESTONE-004」という名前の重複をどう
   整理するか。
3. `backend/app/ai/native/`の由来を確認いただけるか(Claude側の
   会話履歴からは追跡できなかった)。

---

## 8. CEO再検証手順

D55の方針(変更範囲に関わらず、毎回`scripts/verify.ps1`による完全な
品質ゲート通過をもって完了とする)に従い、今回もFlutter/Dartを
変更していないことを理由に再検証を省略しない。

```powershell
.\scripts\verify.ps1 -RunChrome
```

Python Test部分(`forge_ai/tests`を含む)が今回のレポート2章の結果と
一致することをご確認いただきたい。
