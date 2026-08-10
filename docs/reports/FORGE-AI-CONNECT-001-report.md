# FORGE-AI-CONNECT-001 — GeminiProvider実装 実施レポート

**Ref:** FORGE-AI-CONNECT-001(初出の一意ID。既存のM004/M005等とは
無関係の新規作業のため、MASTER HANDOFF文書10章の方針に従い新しい
名前空間を使った)
**担当:** Principal Engineer(Claude)　**日付:** 2026-08-10

CEOから「自作AIか外部API利用か、どちらかをやりたい。課金なしで」という
質問を受け、以下を回答した上で`AskUserQuestion`で選択してもらった。

1. ゼロから自前モデルを学習する「自作AI」は、GPU・データセットが必要で
   無料では現実的でない。
2. ローカルLLM(Ollama等)は永続的に無料だが、CEOのマシンへのセットアップが
   必要。
3. 外部API(Gemini無料枠)は、APIキーさえ取得すれば今すぐコード側を
   実装できる。

CEOの回答は「Gemini無料枠(外部API)を先に」。これに基づき実装した。

---

## 1. 実装したもの

### 1.1 GeminiProvider(実装本体)

`backend/app/ai/foundation/providers.py`の`GeminiProvider`を、
`_UnimplementedProvider`を継承した「呼ぶと`NotImplementedError`」の
スタブから、実際にGoogle Gemini APIを呼び出す実装へ変更した。

**設計判断: SDKパッケージを追加しなかった理由**

`google-genai`等の公式SDKパッケージを追加する案も検討したが、以下の
理由で見送り、既存の`httpx`(`requirements.txt`に既にある、新規追加無し)
でGemini REST APIを直接呼ぶ実装にした。

- SDKパッケージはメソッドシグネチャがバージョンごとに変わりやすく、
  Claudeのサンドボックスに実際のAPIキーが無く動作確認できない状況で
  「動作未確認の外部Dependencyだけが増える」リスクが高いと判断した。
- Gemini REST APIの契約(`POST /v1beta/models/{model}:generateContent`、
  `generationConfig.responseMimeType`/`responseSchema`によるStructured
  Output)は、SDKのラッパーメソッドより安定していると判断した。
- 新規Pythonパッケージ0件という結果は、`providers.py`冒頭のコメントが
  要求する「外部Dependency追加はCEO承認が必要」という条件に対しても、
  最小のリスクで済む選択である。

### 1.2 APIキーの扱い

`GEMINI_API_KEY`環境変数から読む(コンストラクタで`api_key`を明示的に
渡すこともできるが、`ProviderRouter`は`GeminiProvider()`を引数無しで
構築するため、通常は環境変数経由になる)。

キーが無い場合、**コンストラクタでは失敗させない**(`ProviderRouter`の
既存契約「ルーティングの選択自体はキー無しでも失敗しない」を壊さない
ため)。`complete_structured()`が実際に呼ばれた時点で初めて`RuntimeError`
(`NotImplementedError`ではない)を送出する。この区別は、既存テスト
`test_all_foundation_provider_stubs_raise`(「未実装なら
NotImplementedError」という既存の回帰テストの前提)と矛盾しないよう、
意図的に設計した。

### 1.3 テスト

`backend/tests/test_gemini_provider.py`(新規、7件)を追加し、実際に
`pytest`で実行してPASSを確認した。

- APIキー未設定時に`RuntimeError`(`NotImplementedError`ではない)を
  送出すること。
- リクエストボディ(`contents`・`generationConfig.responseSchema`等)が
  期待通りに組み立てられること。
- 正常なレスポンス(JSON文字列を含む`candidates[0].content.parts[0].text`)
  を正しく`dict`へ変換できること。
- HTTPエラーステータス・想定外のレスポンス形状(candidates欠如・
  JSONとして壊れたtext)のいずれも、生の例外を漏らさず`RuntimeError`へ
  変換すること。

**重要な限界**: これらはすべて`httpx.MockTransport`によるモックであり、
**実際のGemini APIへは一度も接続していない**。実際のAPIが本当にこの
形式でリクエストを受理し、この形式でレスポンスを返すかどうかは、
CEO環境で実際のAPIキーを設定して初めて分かる。

既存テストの更新(実際に壊れることを`grep`で確認してから修正、という
今回のセッション内で繰り返している手順どおり):

- `backend/tests/test_ai_foundation.py`
  `TestProviderStubsAreHonestlyUnimplemented.test_all_providers_raise_not_implemented`:
  `GeminiProvider`を対象リストから除外(実装済みのため、他の未実装
  Providerと同じ扱いにできない)。
- `backend/tests/test_ai_runtime.py`
  `test_all_foundation_provider_stubs_raise`: ProviderRouter経由の同種の
  テストから`"gemini"`を除外し、新規に`gemini`が`RuntimeError`を
  送出することを確認するテストを追加。

### 1.4 ドキュメント

- `backend/.env.example`(新規): `GEMINI_API_KEY`の取得方法・設定方法。
- `.gitignore`へ`.env`/`backend/.env`を追加(APIキーの誤コミット防止)。
- `GETTING_STARTED.md`: Gemini APIキー設定手順(3.6節)、curlでの
  呼び出し例(6.1節)、トラブルシューティング2項目を追加。
- `TECH_DEBT.md` TD15を更新(gemini実装済み、他4種は未実装のまま)。

---

## 2. 現状、何ができて何ができないか

### できること
- `backend/.env`に`GEMINI_API_KEY`を設定し、`generation_options.
  provider: "gemini"`を明示的に指定してAPIを呼べば、forge_aiの
  Cognitive Engineの各段階(Meaning/Intent/Planning/Compile等)が、
  Mock(キーワードマッチング)の代わりに実際のGemini APIへ推論を
  依頼するようになる(コードの配線上は成立している)。

### できないこと・注意点
- **実際に動作確認できていない**(1.3節参照)。CEO環境での実行が必須。
- **Flutterアプリ側にGeminiを選ぶUIが無い**。現状、
  `frontend/lib/features/app_generation/data/datasources/
  ai_generation_api.dart`の`generate()`は`generation_options`を一切
  送っておらず、常にBackendの既定Provider(`mock`)が使われる。Geminiを
  試すには、`curl`等でAPIを直接叩く必要がある(`GETTING_STARTED.md`
  6.1節)。Flutter側に「Providerを選ぶ設定画面」を追加するかどうかは
  次のCEO判断が必要。
- openai/claude/oss/forge_ai(Provider名としての、Engineとの接続)は
  引き続き未実装のスタブのまま。

---

## 3. 実際に実行したテスト・結果

```
$ cd backend && python -m pytest -q
526 passed, 12 skipped in 2.99s
(変更前518 passed。新規追加: test_gemini_provider.py 7件 +
 test_ai_runtime.py 1件 = 8件)

$ ruff check backend/app/ai/foundation/providers.py backend/tests/test_gemini_provider.py \
    backend/tests/test_ai_foundation.py backend/tests/test_ai_runtime.py
新規・変更ファイルはエラー0件。test_ai_runtime.pyの既存warning 5件
(今回変更していない箇所の未使用import)はスコープ外として対応していない。
```

---

## 4. 未実行のもの

- 実際のGemini APIへの接続確認(APIキーが必要、CEO環境で実施)。
- Gemini経由でのEnd-to-Endアプリ生成の確認(Backend起動→curl→実際に
  Forge JSONが返る→Flutterで描画、まで一気通貫)。
- `flutter analyze`/`flutter test`(GETTING_STARTED.mdの変更はドキュメント
  のみで、Flutterコード自体は変更していないため直接の影響は無いはずだが、
  Claude環境では引き続き未検証)。

---

## 5. 推測(事実として扱っていないもの)

- 既定モデル名を`gemini-2.0-flash`とした。2026-08-10時点でGoogleが
  無料枠を提供している軽量モデルという理解に基づくが、モデル名・無料枠の
  条件はGoogle側の都合で変わりうる。実際に使う前に
  https://ai.google.dev/pricing 等の公式情報で確認することを推奨する。
- Gemini REST APIの`responseSchema`が、`_RESPONSE_SCHEMAS`
  (`forge_ai_provider_bridge.py`)の各stageのschemaをそのまま受理する
  という前提でコードを書いたが、Gemini側のSchema実装がOpenAPI 3.0
  Schemaのどの部分集合をサポートしているかは、実際に呼んで確認していない。

---

## 6. CEO確認事項

1. `backend/.env`に実際のAPIキーを設定し、`GETTING_STARTED.md` 3.6節・
   6.1節の手順で実際に呼び出し、結果を共有してほしい。
2. Flutterアプリ側にProviderを選ぶUI(設定画面等)を追加するかどうか。
3. モデル名(`gemini-2.0-flash`)が実際に利用可能か、無料枠の条件は
   想定通りか。

---

## 7. 次提案

- CEO確認事項1の結果次第で、レスポンス形式のズレを修正する。
- Flutter側のProvider選択UIを追加する場合は、別Taskとして計画する。
- 他のProvider(OSS/Ollama等)を追加する場合、CEOの選択(2番目の
  ローカルLLM)として引き続き着手可能。
