# Native AI Roadmap

Forgeの最終目標は「ChatGPT/Claude/Geminiを使うアプリ」ではなく、
**Forge独自のAI(Forge Native AI)を将来搭載すること**である
(FORGE-MILESTONE-003「最重要事項」)。本ドキュメントは、現在のStub基盤から
Native AIへ至る道筋を記録する。

---

## 1. Provider非依存にしている理由

`backend/app/ai/runtime/provider_router.py`の`AIProvider`(=`LLMAdapter`)
Protocolは、以下だけを要求する。

```python
def complete_structured(self, prompt: str, response_schema: dict) -> dict: ...
```

これ以外の情報(モデル名・APIキー・SDK固有の型)は一切要求しない。
理由は3つ:

1. **ベンダーロックインの回避**: 特定企業のAPIに密結合すると、料金改定・
   仕様変更・提供終了のリスクをForge全体が負うことになる
   (共通指示書5章「特定企業のAIに密結合しない設計を優先する」)。
2. **Forge独自Validatorとの整合性**: どのProviderが生成した文書でも、
   最終的に通す関門は同じ`schema_validator.validate_forge_document()`である。
   Provider側の出力形式に依存した検証をしていないため、Providerの
   差し替えがValidator側に影響しない。
3. **将来のNative AI(自前モデル)への移行を前提にした設計**: 2章参照。

## 2. Native AIへの移行方法

現在の`ProviderRouter`は5つのProvider名(`openai`/`claude`/`gemini`/`oss`/
`forge_ai`)を登録している。`forge_ai`という名前は、既に実装済みの
`forge_ai/`パッケージ(FORGE PROJECT AI実装チーム キックオフ指示書で構築、
世界理解〜設計までの決定的なCognitive Engine)を将来の「Forge Native AI」
候補として位置づけるための布石である。

移行ステップ(将来、CEO承認のもとで実施):

1. `foundation/providers.py`の`ForgeAIProvider`スタブに、実際に
   `forge_ai/core/pipeline.py`の`run_pipeline()`を呼び出す実装を追加する。
   ただし`forge_ai/`は現状MockProviderでのみ動くため、`forge_ai/`自体に
   実際のLLM Provider(または将来の自前モデル)を接続する作業が
   先に必要になる(`forge_ai/docs/KNOWN_LIMITATIONS.md`参照)。
2. `forge_ai/`の`Intent`/`ApplicationPlan`/`ForgeIRDocument`型と、
   `backend/app/ai/foundation/interfaces.py`の`IntentIR`/`PlanIR`型を
   統合する(現状は別々の型として存在する。統合方法は未決定、
   CEO承認が必要な設計変更と位置づける)。
3. `backend/app/ai/runtime/prompt_pipeline.py`の`PromptPipeline`が、
   `ForgeAIProvider`経由で`forge_ai/`のCognitive Engineを実際に呼び出す
   ようになる。この時点で初めて、Stubから実装への切り替えが起こる。

現時点(FORGE-MILESTONE-003終了時点)では、上記いずれも実施していない
(禁止事項「AI実装したふり」「未実装を実装済みと書く」を厳守するため)。

## 3. Prompt Pipeline(実装への接続点)

`docs/spec/PROMPT_PIPELINE.md`参照。フロー自体(Intent→Plan→JSON→
Validator→Critic→Repair)は既に完成しており、各段階の**実装だけ**を
差し替えれば動く構造になっている。Native AI接続時に`prompt_pipeline.py`
自体を変更する必要は無い(DIで実装を差し替えるだけでよい設計)。

## 4. Repair Loop

`MAX_REPAIR_ATTEMPTS = 2`(共通指示書6.5節)。Native AI接続後も、
この上限は変更しない前提とする(変更する場合はCEO承認が必要な設計変更、
共通指示書の該当節を参照)。

## 5. Context管理

`context_builder.py`の`AIContextBuilder`は、Memory(Working/Project/User
の3層)とConversationを統合する。Native AI接続時、これらのバックエンド
実装(DB等)が必要になる。方針10章のプライバシー原則
(User層は既定OFF、明示的opt-inのみ)は、Native AI移行後も変更しない
前提とする。

## 6. 未決定事項(次フェーズでCEO判断が必要)

- `forge_ai/`の型と`backend/app/ai/foundation/`の型の統合方法(2章)。
- JSON Patch vs Semantic Operationという差分編集方式の決定
  (`docs/DECISIONS.md` D4、依然未決定)。
- Memory/ConversationのDBスキーマ・永続化方式。
- 実際にForge独自のモデル(Native AI)をどう学習・提供するか
  (共通指示書7章の段階的ローカル化方針が前提になる)。

## 7. 今回(FORGE-MILESTONE-003.1)のCEO実機確認とNative AIの関係

**重要な事実確認**: FORGE-MILESTONE-003.1でCEOがChrome実機確認した
「計算アプリつくって」「家計簿をつけるメモを作って」等の生成は、
**すべてMock Mode(`MockAppGenerationRepository` → `MockGenerationDataSource`の
決定的なキーワードマッチング)によるものであり、Forge Native AIが
推論した結果ではない。**

```
現在動いているもの:
  Mock Generator(キーワードマッチング、Python/Dart両方で決定的に実装済み)
    ↓
  Forge Language JSON
    ↓
  Dart Runtime(State Store / Action Dispatcher / Renderer)

Native AI Foundation(FORGE-MILESTONE-003で追加、今回は変更なし):
  Protocol定義 + Stub(NotImplementedError)
    ↓
  実際には一度も呼ばれていない
```

「Native AIが動いた」という表現は、今回のCEO実機確認結果を含め、
一度も正しい表現として使っていない。ログに`START`/`REQUEST`/`SUCCESS`と
出るのは`MockAppGenerationRepository`(Mock)のログであり、
`backend/app/ai/runtime/`のいずれのコンポーネントも呼び出されていない。
