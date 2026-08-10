# FORGE-MILESTONE-003 実施レポート — Analyzer Zero → Chrome Verification → Native AI Foundation

**Ref:** FORGE-MILESTONE-003(v2)　**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-12

CEO実測(Python 167 PASS・**Flutter Test 212 PASS**・Web Build PASS・Runtime/
Chrome/Mock Generator/Language v1.2/Widget v1.1/E2E 全PASS)を土台とする。
今回追加したコードのFlutter側検証はClaude環境では未実施であり、断定しない。

---

## PHASE1〜4: Analyzer完全ゼロ・検証状況

### PHASE1で修正した箇所

CEOから正確なfile:line:colの指定が無かった(「Unused import・List
inference・Map inference 計3件」というカテゴリ名のみ)ため、Pythonで
簡易的な静的検出スクリプトを書いてRepository全体を機械的に監査した
(D47参照)。

| # | 種別 | ファイル・箇所 | 修正内容 |
|---|---|---|---|
| 1 | Unused import | `forge_runtime_state.dart` | `forge_form_validator.dart`のimportを削除(自動検出ツールで発見。手動チェックでは見落としていた) |
| 2 | Map inference | `forge_state_store_test.dart`・`forge_action_dispatcher_test.dart`(計8箇所) | `ForgeStateStore({})` → `ForgeStateStore(<String, ForgeStateValue>{})` |
| 3 | List/Map inference(防御的追加) | `forge_state_store.dart`・`forge_runtime_state.dart`・`v1_1_widgets_test.dart` | `const []`→`const <ForgeChecklistItem>[]`、`const {}`→`const <String, String>{}`(2箇所)、`state ?? {}`→`state ?? <String, dynamic>{}` |

3件という報告に対し、確実性を優先して同種のあいまいな型推論箇所を
まとめて修正した(PHASE1「Repository全体を監査し、同種Warningが
存在するなら今回まとめて修正」に対応)。

### PHASE2〜4: 検証状況

| Phase | 内容 | 状態 |
|---|---|---|
| PHASE2 | `flutter test` 212件以上PASS維持 | **未検証**(Claude環境で実行不可)。テスト削除は行っていない |
| PHASE3 | `flutter build web` 成功維持 | **未検証**。Web関連ファイルは変更していない |
| PHASE4 | Chrome実機確認(Home→Confirm→Generate→Checklist→戻る→再生成) | **未検証**。今回のPHASE1修正は型注釈のみで、挙動を変更していない |

**今回の修正はいずれも型注釈の追加・未使用importの削除のみであり、
Mock生成結果・State更新・Renderer描画ロジックを一切変更していない**
(D37と同じ理由付け)。したがってPHASE2〜4の再検証結果が変わる理由は
無いと考えるが、断定はしない。

---

## PHASE5〜10: Forge Native AI Foundation

詳細は新設した3ドキュメントを参照(重複を避けるため、ここでは要約のみ)。

- `docs/spec/AI_RUNTIME.md` — `backend/app/ai/runtime/`の構成、
  `foundation/`との関係(型を複製せずエイリアス再利用)。
- `docs/spec/PROMPT_PIPELINE.md` — PHASE9のフロー詳細、Repair Loopの安全設計。
- `docs/spec/NATIVE_AI_ROADMAP.md` — Provider非依存の理由、Native AI移行手順。

### 実装した内容(Python、実行・検証済み)

- `backend/app/ai/runtime/prompt_pipeline.py`(新規)。
- `backend/app/ai/runtime/`の既存5ファイル(`planner.py`・`critic.py`・
  `repair.py`・`context_builder.py`・`provider_router.py`)を活用。
- `backend/tests/test_ai_runtime.py`(新規21件)。

```
$ cd backend && python -m unittest discover -s tests -p "test_*.py"
----------------------------------------------------------------------
Ran 188 tests in 0.016s

OK
```

**Provider非依存であることを実際にコードで確認済み**:
`ProviderRouter`のソースコードにOpenAI/Anthropic/Google等のSDK importが
無いことを`test_no_provider_specific_sdk_imported`で確認。5 Provider
(openai/claude/gemini/oss/forge_ai)全てが、実際に呼ぶと
`NotImplementedError`を送出することを確認済み(「AI実装したふり」
していないことの実証)。

---

## PHASE11: Architecture Review(Principal Engineer視点）

Native AIへ将来移行する際の問題点を、指定された14領域について洗い出す。

| 領域 | 現状 | Native AI移行時の懸念 |
|---|---|---|
| **Language** | v1.2、12 Widget・9 Action・6 Validationルール、Freeze方針あり | AIが「どのTemplateが使えるか」を知る手段が、文字列のtuple(`available_templates`)のみで、各Templateが要求するパラメータ形状(構造化スキーマ)が無い |
| **Validator** | 188テスト、多バージョン対応、堅牢 | エラーに深刻度はあるが「AIがどれだけ確信を持って直せそうか」という信号が無い。Repair Engineへの入力としては十分だが、Critic向けの粒度としては粗い可能性 |
| **Runtime(Dart)** | State Store/Action Dispatcher/Form Validator、AI非依存で正しく分離済み | 特になし(意図通りAIを知らない層になっている) |
| **Renderer** | 堅牢、Fallback完備 | TD11(構築時例外のみ保護、レイアウト時例外は未保護)が残存。AIの出力元に関わらず影響する |
| **Template** | Checklist/Memo/Form(構造)+Card(合成)の3+1種 | **テンプレートの「契約」が構造化されていない**。`Planner.plan()`が`template_hint: str \| None`という自由文字列を返す設計であり、AIが安全に選べる正式なTemplate一覧・パラメータスキーマが無い(下記「発見した問題」参照) |
| **Mock Generator** | Python/Dart二重管理(TD10)、9カテゴリ | Native AI移行後も、Mock ModeはBackend不要のオフライン動作として価値が残る。学習データの一次ソースにもなりうる |
| **AI Runtime** | 今回新設、型はfoundation/を再利用 | TD16(forge_ai/との型統合が未決定) |
| **Prompt Pipeline** | フロー完成、Stub動作 | **`LanguageGenerator`がAI呼び出しを内部に持つのか、決定的処理なのかが未定義**(下記「発見した問題」参照) |
| **Provider Interface** | `complete_structured(prompt, schema) -> dict`のみ、最小 | ストリーミング・コスト計測・リトライ/タイムアウトポリシーが型に無い。本番のNative AI運用には不足 |
| **Context** | `AIContextBuilder`/`PromptContext`の型はあるが、`Memory`/`Conversation`は空のProtocolのまま | 永続化戦略(DB等)が完全に未着手。複数ターン対話が必要になった時点でのボトルネック候補 |
| **Plugin** | `PluginRouter` Protocolのみ(FORGE-MILESTONE-002由来)、以降進展なし | Language v1.2のAction 9種はすべて「ローカル」操作(State操作・画面遷移)であり、外部連携(Plugin経由のAction)を表現する手段がまだ無い。共通指示書のPlugin Registry構想との距離が大きいまま |
| **State** | 5型(string/boolean/number/string_list/checklist)、Store一元化 | 計算値・派生State(他Stateから導出される値)の概念が無い |
| **Action** | 9種、Dispatcher一元化、Composite/循環防止あり | 新しいAction種別の追加が「Language version bump」でしか出来ない(Pluginのような動的登録の仕組みが無い) |
| **Validation** | 6ルール型、Widget付近にエラー表示 | 動的検証(サーバー往復が必要な検証、例:重複チェック)を表現する手段が無い |

### 発見した問題(2件、特に重要)

1. **Template契約が構造化されていない**: `ScreenPlan.template_hint`が
   自由文字列であり、AIが実際に安全に使える形になっていない。
   `forge_ai/`側にはTemplateごとの`Params`型(`ChecklistTemplateParams`等)が
   既に存在するため、これを`backend/app/ai/runtime/`側からも参照できる
   形に整理することを、次フェーズの検討事項として記録する(新規のTECH_DEBT
   項目とはせず、NATIVE_AI_ROADMAP.mdの型統合(D44)と合わせて扱う)。

2. **`LanguageGenerator`の実行主体が未定義**: `foundation/interfaces.py`の
   `LanguageGenerator.generate(plan) -> dict`は、内部でAIを呼ぶのか
   (`forge_ai/`のCompilerのように)決定的処理で済ませるのかを明示していない。
   `forge_ai/core/compiler.py`は意図的に「決定的なPython実装、Providerは
   タイトル判断にのみ使う」という設計判断(forge_ai/ D2)をしている。
   `backend/app/ai/runtime/`側もこの判断を踏襲することを推奨するが、
   今回は明示的に決定していない(CEO確認事項として11章末尾に記載)。

---

## PHASE12: 技術的負債

`TECH_DEBT.md`に「解消済み」セクションを新設(Analyzer Warning)、
TD15〜TD17を追加した(Provider未実装・Native AI未接続・Repair Engineの
設計思想の不一致)。詳細は同ファイル参照。

---

## 完了条件チェックリスト

| 条件 | 状態 |
|---|---|
| `flutter analyze` No issues found! | **未検証**(3件+防御的追加分を修正したが、CEO環境での再実行が必要) |
| `flutter test` 212件以上PASS | **未検証**(テスト削除は行っていない) |
| `flutter build web` PASS | **未検証**(Web関連ファイルは変更していない) |
| Chrome実機確認完了 | **未実施**(Claude環境にChromeは無い) |
| Python Test 167件維持 | ✅ **実行確認済み**(188件、167件は無改変のまま含まれる) |
| Runtime正常 | 型注釈のみの変更のため影響なしと判断(未検証) |
| AI Runtime Foundation完成 | ✅ Protocol定義+Stub、実行確認済み(21テスト) |
| Prompt Pipeline完成 | ✅ フロー完成、Repair Loop動作確認済み |
| Provider非依存設計完成 | ✅ SDK非import・全Stub NotImplementedErrorを確認済み |

---

## CEO確認事項

1. **`flutter analyze`/`flutter test`/`flutter build web`/Chrome実機の
   再検証**(最優先)。CEO再検証コマンドは次章。
2. **PHASE11で発見した「LanguageGeneratorの実行主体」**(AI呼び出しか
   決定的処理か)。`forge_ai/`の設計判断(決定的処理を推奨)を
   `backend/app/ai/runtime/`側にも適用してよいか。
3. **PHASE11で発見した「Template契約の構造化」**。`forge_ai/`の
   `XxxTemplateParams`型を`backend/app/ai/runtime/`から参照する設計へ
   進めてよいか(次フェーズの設計変更、CEO承認が必要な範囲と判断した)。
4. **TD16(forge_ai/とruntime/の型統合)の方針・時期**。

## CEO再検証コマンド

```powershell
cd "C:\forge_verify\<展開先>\forge\frontend"
flutter clean
flutter pub get
flutter analyze
flutter test --reporter expanded
flutter build web --debug
flutter run -d chrome
```

```powershell
cd "C:\forge_verify\<展開先>\forge\backend"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt --break-system-packages
pytest -v
```

Pythonは188件(既存167件+今回21件)全てPASSすることを想定している。
