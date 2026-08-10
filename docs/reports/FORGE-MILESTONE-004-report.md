# FORGE-MILESTONE-004 実施レポート — Native AI Phase-1（Intent Engine）

> **【2026-07-14 注記、Architecture Freeze】** このレポートが扱う
> 「FORGE-MILESTONE-004」は、現在「**M005: Backend AI Integration**」
> として正式に読み替えられている。「M004」は現在`forge_ai/`
> (Forge AI Core)のみを指す。番号整理・責務境界・依存方向の正典は
> `docs/spec/FORGE_AI_ARCHITECTURE_V1.md`を参照すること。
> 以下の本文は当時の記録のまま変更していない。

**Ref:** FORGE-MILESTONE-004(→ 現M005)　**担当:** Principal Engineer / Architect（Claude）
**日付:** 2026-07-13

CEO実測(Flutter Test 223 PASS、Runtime基盤完成)を前提とする。今回は
`backend/`(Python)のみを変更し、Flutter/Dartは一切変更していない。

---

## 0. 最重要判断: 既存資産との重複回避

作業開始前に、`backend/app/ai/foundation/`(FORGE-MILESTONE-002)・
`backend/app/ai/runtime/`(FORGE-MILESTONE-003)を実際に読み直した。
今回要求されたPHASE1〜9の多くが、既存コンポーネントと概念的に
重複していることを確認した。「5年後でも破綻しないアーキテクチャ」
という今回の目的を踏まえ、**類似概念の型を複数並立させないこと**を
最優先し、以下の方針で対応した。

| PHASE | 要求 | 対応方針 |
|---|---|---|
| 1 | Intent IR設計 | **拡張**: 既存`IntentIR`へ5フィールド追加 |
| 2 | IntentParser Interface | **新規**: 既存`AIPlanner`より粒度の細かいProtocolを追加 |
| 3 | Planner(Intent→AppPlan) | **既存で充足**: `AIPlanner.plan()`が同一概念(`AppPlan`=`PlanIR`) |
| 4 | Template Engine | **新規**: 既存3 Templateの構造化カタログ化(新規Template実装は無し) |
| 5 | Template Selector | **新規**(Stub) |
| 6 | Language Generator Interface | **既存で充足**: `foundation.LanguageGenerator` |
| 7 | Repair Loop | **既存で充足**: `prompt_pipeline.PromptPipeline`(MAX_REPAIR_ATTEMPTS=2) |
| 8 | Provider Router | **拡張**: 既存`ProviderRouter`へ`native`/`local`エイリアス追加 |
| 9 | AI Runtime(まとめ) | **新規**: `NativeAIRuntime`bundle |

---

## 1. 今回実際に実行したもの(事実)

```
$ cd backend && python -m unittest discover -s tests -p "test_*.py"
Ran 221 tests in 0.014s
OK

$ cd .. && python -m unittest discover -s forge_ai/tests -p "test_*.py"
Ran 80 tests in 0.013s
OK
```

- 新規テストファイル`tests/test_native_ai_phase1.py`(27件)を実際に
  実行し、全合格を確認した。
- 既存の221件(backend、うち今回変更した`provider_router.py`関連の
  更新2件・新規2件を含む)・80件(forge_ai、無改変)を実際に再実行し、
  **後方互換性が壊れていないことを実行して確認した**。
- `Template.builder`が既存の`build_checklist_template`等へ正しく委譲し、
  実際に`schema_validator.validate_forge_document()`へ合格する文書を
  生成することを実行して確認した。
- `NativeAIRuntime().is_fully_stubbed()`が`True`を返すことを実行して
  確認した(全推論系コンポーネントがStubのままであることの機械的確認)。
- `ProviderRouter`の`native`/`local`エイリアスが、それぞれ`forge_ai`/
  `oss`と同一インスタンスであることを`assertIs`で実行して確認した。

---

## 2. 今回実行できなかったもの(事実)

- **Flutter側の一切**(`flutter analyze`・`flutter test`・
  `flutter build web`・Chrome実機確認)。今回はPython(backend/)のみを
  変更しており、Flutterコードは1バイトも変更していないため、
  指示書PHASE10の通り「Flutter変更がある場合はCEO実測」に該当しない
  (変更が無いため、追加のCEO実測は不要と判断する)。
- 実際のAI推論(全コンポーネントがStubのまま。指示書「絶対ルール」に
  従い、意図的に未実装)。
- `docs/spec/AI_RUNTIME.md`等のドキュメント更新後の、Markdown
  レンダリング上の見た目確認(テキストエディタでの内容確認のみ)。

---
## 3. 推測(断定していないこと)

- **PHASE3「AppPlan」がPlanIRと同一概念である、という判断**: 指示書の
  「AppPlan」という名前と、既存`PlanIR`(`screens`/`navigation_edges`/
  `template_hint`)の構造が十分に近いと判断したが、CEOが「AppPlan」に
  何か異なる意味を意図していた可能性は排除できない。もし異なる概念で
  あれば、追加の設計が必要になる。
- **PHASE6「Language Generator Interface」が既存のfoundation.LanguageGenerator
  で充足している、という判断**: 同様に、既存Protocolの再利用で
  足りると判断したが、CEOがより具体的な別の設計を意図していた
  可能性は排除できない。
- **Platform/Complexityの具体的な値の妥当性**: `Platform`
  (mobile/web/desktop/cross_platform)・`Complexity`(simple/medium/
  complex)という値の粒度は、Forgeの現状(Flutter、複数プラットフォーム
  出力)を踏まえた推測であり、実際にAIがこれらの値をどう使うかは
  未検証(推論が無いため検証しようがない)。

---

## 4. 技術的負債(今回新たに発見・記録したもの)

`TECH_DEBT.md`にTD20〜TD22として記録した。要約:

- **TD20**: Native AI出力の安全性検査(Output Safety)が未設計
  (個人情報過剰収集等を検出する仕組みが無い)。
- **TD21**: Prompt Injection対策が明示的に設計されていない。
- **TD22**: IntentIR/PlanIR/Templateスキーマにバージョン管理が無い
  (Forge Language自体はv1.0/v1.1/v1.2という明確なバージョニングを
  持つが、AI Runtime側の中間表現には無い)。

既存の負債(TD10: Python/Dart Mock Generator二重管理、TD16: forge_ai/と
runtime/の型統合未定、TD17: Repair Engineの設計思想不一致)は、今回
解消していない(継続)。

---

## 5. CEOが実測すべき項目

今回はFlutterコードを変更していないため、**Flutter側の追加実測は
不要**と判断する。Python側について、以下をCEO環境で再実行いただき、
Claude環境での実行結果(1章)と一致することを確認いただきたい。

```powershell
cd backend
python -m unittest discover -s tests -p "test_*.py"
# 期待値: Ran 221 tests ... OK

cd ..
python -m unittest discover -s forge_ai/tests -p "test_*.py"
# 期待値: Ran 80 tests ... OK
```

または`.\scripts\verify.ps1 -SkipBuild`でも、Python Test部分は同様に
実行される(Flutter analyze/testも合わせて走るが、今回はFlutter側に
変更が無いため、既存の223 PASS/警告0の状態から変化しないと予想する。
断定はしない)。

---

## PHASE11: Architecture Review(16観点)

| # | 観点 | 所見 |
|---|---|---|
| 1 | **Architecture** | `foundation/`(型・初期Protocol)→`runtime/`(refined Protocol・orchestration)→`native_ai_runtime.py`(bundle)という一方向の依存が保たれている。ただし`forge_ai/`(独立パッケージ)との関係は依然未統合(TD16、既知)。 |
| 2 | **Scalability** | `TemplateRegistry`は「`Template`エントリを1つ追加するだけ」で拡張できる設計(Selector/Plannerの変更不要)。`ProviderRouter`のエイリアスパターンも同様に拡張しやすい。 |
| 3 | **Maintainability** | 全新規ファイルに「なぜ既存と別か/既存の何を再利用したか」を明記した。一方でエイリアス(`Intent`=`IntentIR`・`native`=`forge_ai`インスタンス等)が増えており、新規参加者向けの一枚の対応表(用語集)が今後必要になる可能性がある。 |
| 4 | **AI Safety** | TD20(Output Safety未設計)参照。現状は推論が無いため実害無し。 |
| 5 | **Prompt Injection** | TD21参照。`PromptBuilder`(forge_ai/)の構造化Prompt(文字列連結禁止)が基礎的な防御にはなるが、明示的なサニタイズ層は無い。 |
| 6 | **Future LLM** | `AIProvider.complete_structured(prompt, response_schema)`という最小限のインターフェースはSDK非依存。ただし「構造化出力に対応したモデル」を前提にしている点は、将来のモデルが全てこの能力を持つとは限らないという仮定を含む(明記した)。 |
| 7 | **Local AI** | `local`エイリアス追加のみ。実際のOllama等ローカル実行系との接続は今回スコープ外(意図通り)。 |
| 8 | **Runtime(Flutter)** | 完全に非依存であることを確認済み(今回Dartファイルを1つも変更していない)。 |
| 9 | **UX** | 今回はUI変更を伴わない。`Platform`/`Complexity`をユーザーが将来指定できるようにするか(例: 「Webだけで動けばいい」という指定)はUX判断であり、今回は据え置いた。 |
| 10 | **Memory** | `AIContextBuilder`/`Memory`/`Conversation`は既存のまま(Stub)。今回変更していない。 |
| 11 | **Performance** | `TemplateRegistry`のタグ/カテゴリ/能力検索は現状O(n)の線形探索(n=3)。Template数が数百規模に増えた場合はインデックス化が必要になりうるが、現時点では時期尚早な最適化と判断し行っていない。 |
| 12 | **Testability** | 全新規コンポーネントがDIで差し替え可能。`NativeAIRuntime.is_fully_stubbed()`により「動いたふりをしていないか」を実行可能なテストとして検証できる、という具体的な仕組みを追加した。 |
| 13 | **Backward Compatibility** | `IntentIR`拡張・`ProviderRouter`エイリアス追加とも、既存テストを実行して後方互換性を確認済み(1章)。唯一「弱体化ではない形」で更新した既存テストは1件(`test_all_five_providers_registered`→7件版、D53参照)。 |
| 14 | **Versioning** | TD22参照。Forge Language(v1.0/v1.1/v1.2)と異なり、AI Runtime側の中間表現にはバージョニングが無い。将来Provider実装が複数同時稼働する際の課題として記録した。 |
| 15 | **Cost/Observability** | `AIProvider`インターフェースに、トークン数・コスト・レイテンシを記録するフックが無い。実推論接続時に追加が必要になる観点として、今回初めて明示的に指摘する(TECH_DEBTには未記載、次回以降の検討事項)。 |
| 16 | **Language非依存性の確認** | Template追加がForge Language自体の変更を要求しない設計(Widget語彙は既存のまま)であることを、既存3 Templateのカタログ化を通じて再確認した。 |

---

## 完了条件との対応

| 条件 | 状態 |
|---|---|
| Intent IR設計 | ✅ 既存拡張、実行確認済み |
| IntentParser Interface(実装無し) | ✅ Protocol+Stub |
| Planner(型のみ) | ✅ 既存で充足 |
| Template Engine(構造化) | ✅ 実装済み(カタログ化のみ、AI推論無し) |
| Template Selector(Stub) | ✅ |
| Language Generator Interface(Protocolのみ) | ✅ 既存で充足 |
| Repair Loop(設計のみ) | ✅ 既存で充足 |
| Provider Router(Stub) | ✅ 拡張 |
| AI Runtime(まとめ、推論禁止) | ✅ `NativeAIRuntime`、`is_fully_stubbed()`で検証可能 |
| Python側テスト | ✅ 実行・全合格(221+80件) |
| 14観点以上のレビュー | ✅ 16観点 |
| 動いたふり禁止 | ✅ 全てNotImplementedError/Stub、機械的に検証可能 |
