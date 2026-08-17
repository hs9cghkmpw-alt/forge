"""LLMAdapter の Provider別実装(FORGE-MILESTONE-002 PHASE6、
FORGE-AI-CONNECT-001でGeminiのみ実装)。

**Gemini・Mock以外はすべて未実装。** `complete_structured()` は呼ばれると
`NotImplementedError`を投げる。目的は「型としてどのProviderも差し替え
可能である」ことを示すことであり、実際にAPIキーを使って外部サービスへ
接続する処理は含まない。

FORGE-MILESTONE-005 Task7で、`MockLLMAdapter`のみを実際に動作する
実装として追加した(指示書「実装するProviderはMockのみ」)。

FORGE-AI-CONNECT-001(2026-08-10): CEOから「無料で使える外部AI接続を
先に実装してほしい」という明示的な承認を得たため、`GeminiProvider`を
実装した(Google AI Studioの無料枠を想定)。新規の外部Pythonパッケージは
**追加していない**。`google-genai`等のSDKパッケージはメソッドシグネチャの
バージョン差異が大きく、動作未確認のまま依存だけ増えるリスクが高いと
判断し、代わりに既存の`httpx`(既にrequirements.txtにある)でGemini REST
APIを直接呼ぶ実装にした。REST APIの契約(`generateContent`エンドポイント)
はSDKのメソッド名より安定していると判断した。

**注記(2026-08-10追記、実機確認済み)**: 当初はGoogle公式ドキュメントの
契約に基づいて実装しただけで、`httpx.MockTransport`によるUnit Testでしか
検証できていなかった。同日中にCEOから実際のAPIキーを共有してもらい、
このセッション内で`uvicorn`を起動して`POST /api/v1/ai/generate`へ実際に
リクエストを送り、Gemini経由でForge Language準拠のJSON文書が生成され
Validatorを通過することを確認した(`TECH_DEBT.md` TD15に詳細記録)。
既定モデルも、この実機確認の過程で`gemini-2.0-flash`(429エラー)→
`gemini-2.5-flash`(404エラー)→`gemini-flash-latest`(成功)という
試行錯誤を経て決定した。

将来Gemini以外(OpenAI/Claude/OSS)を実装する際に必要になる外部Dependency
(例: `openai`パッケージ等)は、指示書「CEO承認が必要: 外部Dependency追加」
に該当するため、実装着手前に必ずCEO確認を取ること。
"""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Any

import httpx

from .interfaces import LLMAdapter


class _UnimplementedProvider:
    """全Providerスタブの共通基底。"""

    provider_name: str = "unimplemented"

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.provider_name} はまだ実装されていません(FORGE-MILESTONE-002 PHASE6は"
            f"インターフェース設計のみ)。実装するには外部Dependency追加のCEO承認が必要です。"
        )


class OpenAIProvider(_UnimplementedProvider):
    """OpenAI(GPT系)向けAdapterのスタブ。"""

    provider_name = "openai"


class ClaudeProvider(_UnimplementedProvider):
    """Anthropic Claude向けAdapterのスタブ。"""

    provider_name = "claude"


class GeminiProvider:
    """Google Gemini向けAdapter(FORGE-AI-CONNECT-001で実装)。

    無料枠での利用を想定している(Google AI Studio:
    https://aistudio.google.com/apikey でAPIキーを取得)。既定モデルは
    `gemini-flash-latest`(常に最新のFlash系モデルを指すエイリアス)。

    **2026-08-10、CEOの実際のAPIキーで実機確認した記録**: 当初
    `gemini-2.0-flash`を既定にしていたが、実際に呼び出したところ
    `429`(無料枠のトークン上限が`0`)で失敗した。`gemini-2.5-flash`・
    `gemini-2.5-flash-lite`は`404`(「新規ユーザーには提供終了」)で
    失敗した。`gemini-flash-latest`のみ実際に成功し、日本語での
    構造化JSON応答(`{"title": "買っとこ！買い物メモ"}`等)を正しく
    受け取れることを確認した。バージョン固定の名前より、
    `-latest`エイリアスの方がGoogle側のモデル入れ替わりに対して
    壊れにくいと判断し、既定値をこちらにした。無料枠の条件・利用可能な
    モデル名は今後もGoogle側の都合で変わりうるため、将来またエラーに
    なった場合は同じ手順(実際に複数モデル名を試す)で確認すること。

    `api_key`を省略すると環境変数`GEMINI_API_KEY`を読む。どちらも
    無い場合、コンストラクタでは失敗させず(`ProviderRouter`が
    `GeminiProvider()`を引数無しで構築しているため)、
    `complete_structured()`呼び出し時に初めて`RuntimeError`を送出する
    (ADR「ルーティングの選択自体はキー無しでも失敗しない」という既存の
    契約を壊さないため)。
    """

    provider_name = "gemini"

    _API_BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "gemini-flash-latest",
        client: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
        self._model = model
        self._client = client  # テスト用にhttpx.MockTransportを注入できるようにする
        self._timeout = timeout

    @property
    def model(self) -> str:
        """実際に呼ぶModel名。

        FORGE-ROADMAP R0(2026-08-17)で公開した。`AIRouter`がExperienceへ
        Model名を残そうとしたところ、`GeminiProvider`だけが`_model`
        (private)しか持たず**空文字で記録されていた**——実機で確認した
        (`{"provider": "gemini", "model": ""}`)。

        Providerが分かってModelが分からない記録は、Model入れ替えの前後を
        区別できないので、後から学習素材として使えない
        (`OpenAICompatibleAdapter.model`と同じ形に揃えた)。
        """
        return self._model

    def with_deadline(self, seconds: float) -> "GeminiProvider":
        """Task全体の残り時間に締めたProviderを返す
        (`app/ai/foundation/deadline.py`の`SupportsDeadline`、011 §4)。

        **自分自身を書き換えない。** `ProviderRouter`が保持する共有
        インスタンスなので、書き換えると同時に走る別のリクエストの
        予算まで動いてしまう。

        `min`を取るのは、Provider側のtimeoutより長く待つ理由が無い
        ためである。
        """
        clone = copy.copy(self)
        clone._timeout = max(0.1, min(self._timeout, seconds))
        return clone

    def with_model(self, model: str) -> "GeminiProvider":
        """そのModelを使うProviderを返す
        (`app/ai/foundation/model_choice.py`の`SupportsModelChoice`)。

        `with_deadline`と同じく**自分自身を書き換えない**。
        """
        if not model or model == self._model:
            return self
        clone = copy.copy(self)
        clone._model = model
        return clone

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        """`response_schema`が空dict(`{}`)の場合、`responseSchema`自体を
        省略し、`responseMimeType: application/json`のみでフリーフォームの
        JSON出力を要求する(FORGE-PRODUCT-VISION-002 TD40対応、
        2026-08-11)。

        **技術検証の記録**: `responseSchema`(OpenAPI Schemaのサブセット、
        `$ref`未対応)で「type: object」だけを指定し`properties`を
        書かない形(Forge DocumentのWidget木のような、再帰的で事前に
        形を確定できない構造)を試したところ、Geminiはその部分を
        **空オブジェクト`{}`で返す**ことを実機で確認した(既存の
        構造化データを丸ごと失う、深刻な失敗モード)。一方、
        `responseSchema`を送らずフリーフォームJSONとして生成させると、
        既存の構造を正しく維持しながら新しい要素を追加できることも
        実機で確認した。したがって「事前に形が分からない/再帰的な
        JSONを生成させたい」場合は、呼び出し側が`response_schema={}`を
        渡すことで、この分岐に入る(`forge_operation.py`参照)。
        """
        if not self._api_key:
            raise RuntimeError(
                "GEMINI_API_KEY が設定されていません。Google AI Studio "
                "(https://aistudio.google.com/apikey) で取得した無料APIキーを"
                "環境変数 GEMINI_API_KEY に設定してください(backend/.env.example参照)。"
            )

        url = f"{self._API_BASE}/models/{self._model}:generateContent"
        generation_config: dict[str, Any] = {"responseMimeType": "application/json"}
        if response_schema:
            generation_config["responseSchema"] = response_schema
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }

        client = self._client
        owns_client = client is None
        if client is None:
            client = httpx.Client(timeout=self._timeout)
        try:
            response = client.post(url, params={"key": self._api_key}, json=body)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                # FORGE-AI-QUALITY-001(2026-08-11)対応: 実機で複数プロンプトを
                # 連続送信した際、無料枠のレート制限(実測: 1分あたり20回
                # 程度、Google側の都合で変わりうる)に達し、Gemini APIの
                # 生のエラーJSON("RESOURCE_EXHAUSTED"等の英語の技術用語)が
                # そのままエラーメッセージとしてユーザーに表示されることを
                # 発見した。「app store品質」として、原因と対処法が一目で
                # わかる日本語の文言を先頭に出すよう変更した(生の詳細は
                # 末尾に残し、デバッグ時の手がかりも失わないようにする)。
                raise RuntimeError(
                    "Gemini APIの無料枠の利用上限に達しました。しばらく"
                    "時間をおいてから、もう一度お試しください。"
                    f"(詳細: status={exc.response.status_code}, {exc.response.text[:300]})"
                ) from exc
            raise RuntimeError(
                f"Gemini APIがエラーを返しました(status={exc.response.status_code}): "
                f"{exc.response.text[:500]}"
            ) from exc
        finally:
            if owns_client:
                client.close()

        try:
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Gemini APIのレスポンス形式が想定と異なります: {payload!r}"
            ) from exc


class OSSProvider(_UnimplementedProvider):
    """OSSモデル(Llama/Qwen/Mistral/Phi/Gemma等、Ollama等のローカル推論を想定)
    向けAdapterのスタブ。FORGE-MERGE-001 9章で検討したOllama連携は、
    実装時にこのクラスが受け皿になる想定。"""

    provider_name = "oss"


class ForgeAIProvider(_UnimplementedProvider):
    """将来の自作Forge専用AI向けAdapterのスタブ。FORGE-ARCH-001の最終目標
    (Forge専用モデル)がここに実装される想定。

    注記(FORGE-MILESTONE-005): この`provider_name = "forge_ai"`は
    Provider名としての`forge_ai`であり、Cognitive Engineとしての
    `forge_ai/`パッケージそのものとは別概念である
    (`docs/spec/ADAPTER_CONTRACT_V1.md` 4.0節、Engine/Provider分離)。
    """

    provider_name = "forge_ai"


_WORD_RE = re.compile(r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]+")

# FORGE_v0.2_最終修正指示(Final Gate)P3対応で新設。
# `_flatten_prompt_to_string()`は`prompt.context`を`repr()`でそのまま
# 文字列化するため(`forge_ai_provider_bridge.py`参照)、この文字列には
# `{'plan': {'title': '...', 'screens': [...], ...}}`のような、Pythonの
# dict構文がそのまま現れる。このパターンで既存の`title`/`goal`/`purpose`
# キーの値を直接抜き出せる場合は、それを**そのまま再利用する**
# (キー名自体("title"・"screens"・"plan"等)が単語抽出に混入し、
# 「plan title x 買い物リストです screens」のような、内部表現が漏れた
# 破綻したタイトルになるバグを修正する。実際に発生することを確認した
# 上で修正した)。
_LABELED_VALUE_RE = re.compile(r"'(title|goal|purpose)':\s*'([^']*)'")

# --- Realistic Mock(FORGE-HANDOFF-LOCAL-AI-UX-004 §35 / -005 §26)-------
#
# **解いている問題**: 実機検証で、Mock Provider利用時に生成されたToolへ
# `mock_result` `plan` `title` `screens`といった**内部構造がそのまま
# 露出**し、会話も「mock resultがあると楽そう」という不自然な内容に
# なっていた。指示書は「Mockだから内部JSONっぽい画面が出てもいい、
# という考えは禁止」「MockでもUI Flow / Navigation / Runtimeを
# Productionと同じUX契約で検証できること」と明示している。
#
# 方針: Mockは**LLMのふりをしない**が、**ユーザーの実際の発話から
# もっともらしい日本語を決定的に組み立てる**。乱数は使わない
# (同じ入力なら常に同じ出力=テストが安定する)。

# ユーザー発話を拾う手がかり。会話プロンプトは「ユーザー: 〜」、
# Bridge経由のプロンプトは`[CONTEXT]`内の`'user_text'`/
# `'natural_language'`に入る。
_USER_TURN_RE = re.compile(r"ユーザー:\s*(.+)")
_CONTEXT_TEXT_RE = re.compile(r"'(?:user_text|natural_language)':\s*'([^']*)'")

# 助詞・語尾を落として「何についての道具か」を取り出すための除去語。
# 形態素解析は使わない(Mockに重い依存を持ち込まない)。
_TOPIC_NOISE = (
    "を記録したい", "を管理したい", "をつけたい", "を作りたい", "が欲しい",
    "を残したい", "をメモしたい", "したい", "を作って", "作って",
    "忘れちゃう", "忘れる", "困ってる", "ちょっと",
)

# 話題→(アプリ名, もっともらしい初期データ)。
#
# * 初期データ: Mockが「牛乳・卵・パン」のような**実在しそうな値**を
#   返すことで、生成Toolが製品として成立して見える。
# * アプリ名: 実機で「買い物で何買うかを記録・管理するための道具」という
#   **説明文がそのままタイトル**になっていた。App Storeに並ぶアプリの
#   名前は説明文ではなく短い名詞句なので、話題ごとに短い名前を持たせる。
_TOPIC_PROFILES: tuple[tuple[tuple[str, ...], str, tuple[str, ...]], ...] = (
    (("買い物", "買うもの", "スーパー"), "買い物リスト", ("牛乳", "卵", "パン")),
    (("持ち物", "準備", "旅行"), "持ち物リスト", ("充電器", "着替え", "歯ブラシ")),
    (("タスク", "todo", "やること", "仕事"), "やることリスト", ("メールを返す", "資料を作る", "掃除")),
    (("本", "読書"), "読書記録", ("こころ", "ノルウェイの森", "銀河鉄道の夜")),
    (("血圧", "体温", "体重", "健康"), "健康記録", ("朝の計測", "夜の計測")),
    (("家計", "出費", "支出", "お金"), "家計簿", ("食費", "交通費", "日用品")),
    (("習慣", "運動", "勉強"), "習慣記録", ("ストレッチ", "読書", "英単語")),
    (("在庫", "ストック"), "在庫リスト", ("トイレットペーパー", "洗剤", "米")),
    (("日記", "記録"), "日記", ("今日のできごと",)),
    (("会議", "議事録", "打ち合わせ"), "議事メモ", ("定例ミーティング",)),
)

_DEFAULT_EXAMPLES: tuple[str, ...] = ("最初の項目", "2つめの項目")

# アプリ名として許容する長さ。これを超えるものは「名前」ではなく
# 「説明文」である、という判断に使う。
_MAX_MOCK_TITLE_LENGTH = 14


def _extract_user_utterance(prompt: str) -> str:
    """プロンプトからユーザーの実際の発話を取り出す。

    会話プロンプトでは複数ターンあるため**最後のユーザー発話**を使う
    (今まさに応答すべき相手の言葉だから)。
    """
    turns = _USER_TURN_RE.findall(prompt)
    if turns:
        return turns[-1].strip()
    matched = _CONTEXT_TEXT_RE.search(prompt)
    return matched.group(1).strip() if matched else ""


def _topic_of(utterance: str) -> str:
    """発話から「何についての道具か」を粗く取り出す。

    形態素解析はしない。語尾・助詞を落とすだけの決定的な処理であり、
    完全な理解ではない——それでも`mock_result`よりは遥かに実物に近い。
    """
    topic = (utterance or "").strip()
    for noise in _TOPIC_NOISE:
        topic = topic.replace(noise, "")
    topic = topic.strip("、。 　の")
    return topic or "メモ"


def _examples_for(utterance: str) -> tuple[str, ...]:
    for keywords, _title, examples in _TOPIC_PROFILES:
        if any(k in utterance for k in keywords):
            return examples
    return _DEFAULT_EXAMPLES


def _title_for(text: str, fallback_topic: str) -> str:
    """アプリ名(短い名詞句)を返す。

    まず話題テーブルの短い名前を探す。見つからない場合は`fallback_topic`
    を使うが、それが**説明文の長さ**(`_MAX_MOCK_TITLE_LENGTH`超)なら
    名前として採用せず、既定の短い名前へ落とす。実機で
    「買い物で何買うかを記録・管理するための道具」がタイトルとして
    表示されていた問題への対応。
    """
    for keywords, title, _examples in _TOPIC_PROFILES:
        if any(k in text for k in keywords):
            return title
    topic = (fallback_topic or "").strip()
    if topic and len(topic) <= _MAX_MOCK_TITLE_LENGTH:
        return topic
    return "メモ"


class MockLLMAdapter:
    """実際に動作するProvider実装(FORGE-MILESTONE-005 Task7)。

    FORGE-AI-CONNECT-001(2026-08-10)で`GeminiProvider`も実際に動作する
    実装になったため、「唯一の」実装ではなくなった。こちらは実LLMを
    一切呼ばない、決定的なMock実装であることに変わりはない。
    `ForgeAIProviderBridge`から
    `complete_structured(prompt: str, response_schema: dict) -> dict`
    として呼ばれることを想定する。

    設計方針: `response_schema["properties"]`に列挙されたフィールド名を
    見て、名前ベースの簡易ヒューリスティックで値を合成する
    (`forge_ai.provider.mock_provider.MockProvider`と同じ「決定的・
    キーワードベース」という思想を、フラットな文字列プロンプトの上で
    再現したもの。forge_ai/側のMockProviderを直接importして使い回すことは
    しない。Adapter層のみがforge_ai/へ依存する、というADR 7.3節の制約を
    守るため)。

    既知の制限: 単純な名前ベースヒューリスティックであり、本物の
    自然言語理解ではない。`docs/spec/ADAPTER_CONTRACT_V1.md`が要求する
    「Mockのみ実装」の範囲内での、決定的な代替実装である。
    """

    provider_name = "mock"

    model = "mock-deterministic"
    """R0: Mockも名乗る。空にしておくと「Model名が取れないAdapter」と
    「Mockだった」が記録上で区別できない。"""

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        # [CONTEXT]セクション以降だけから単語を抽出する。[SYSTEM]/[INSTRUCTION]
        # は定型文であり、そこから単語を拾うと実際のユーザー入力・中間データとは
        # 無関係な語(定型文の単語)ばかりになってしまう(実際に実行して確認した、
        # 品質上の問題)。
        context_marker = "[CONTEXT]\n"
        idx = prompt.find(context_marker)
        relevant_text = prompt[idx + len(context_marker):] if idx != -1 else prompt

        words = tuple(dict.fromkeys(w.lower() for w in _WORD_RE.findall(relevant_text)))
        # 既にPlan/Intentが持っている`title`/`goal`/`purpose`をそのまま
        # 再利用できる場合の候補(P3対応、下記`_synthesize_field`参照)。
        labeled_values = {m.group(1): m.group(2) for m in _LABELED_VALUE_RE.finditer(relevant_text)}
        properties: dict[str, Any] = response_schema.get("properties", {})

        result: dict[str, Any] = {}
        for name, spec in properties.items():
            result[name] = self._synthesize_field(name, spec, words, prompt, labeled_values)
        return result

    def _synthesize_field(
        self,
        name: str,
        spec: dict[str, Any],
        words: tuple[str, ...],
        prompt: str,
        labeled_values: dict[str, str],
    ) -> Any:
        field_type = spec.get("type")

        if field_type == "array":
            # Realistic Mock: 生成Toolの初期データは、内部識別子ではなく
            # 「牛乳・卵・パン」のような**実在しそうな値**にする
            # (実機で`plan` `title` `screens`がそのままチェックリストの
            # 項目として表示されていた問題への対応、指示書§35)。
            if name == "example_items":
                # 話題キーワードの照合は**プロンプト全体**に対して行う。
                # compile段のプロンプトには生の発話が含まれず、
                # `plan.title`等に話題が現れるため(発話だけを見ると
                # 常に既定値になってしまう、実行して確認した)。
                return list(_examples_for(_extract_user_utterance(prompt) or prompt))
            # 既知のフィールド名ごとに、意味の近い単語だけへ絞り込む
            # (forge_ai.MockProviderの`_handle_meaning`と同じ発想:
            # 完全な自然言語理解はしないが、明らかに無関係な結果にはしない)。
            if name == "screens":
                # "screens"はオブジェクト(name/purpose/key_elements)の配列を
                # 期待される(forge_ai.core.planner.Planner.plan()参照)。
                # 単純な文字列リストを返すと`s.get("name", ...)`で例外になる
                # (実際に実行して確認した実バグ)。あえて空リストを返し、
                # forge_ai側が既に持つ「screensが空ならintentの概念から
                # 単一画面のデフォルトを組み立てる」というフォールバックへ
                # 委ねる(forge_ai/自身のロジックを信頼し、Mock側で
                # オブジェクト構造を再現しようとしない)。
                return []
            if name in ("mentioned_actions", "required_actions"):
                action_like = tuple(w for w in words if w.endswith(("する", "したい", "add", "track")))
                return list(action_like) or list(words[:3])
            return list(words[:5])

        if field_type == "integer":
            return 0

        if field_type == "number":
            # FORGE-PRODUCT-VISION-002続き(2026-08-11)で発見した実バグの
            # 修正: JSON Schemaの"number"(浮動小数点、"integer"とは別の型)
            # を判定する分岐が無く、下のデフォルト分岐(文字列"mock_result"
            # を返す)へ落ちていた。呼び出し側(`ConversationEngine.
            # step()`のconfidenceフィールド等)が`float(...)`で数値変換
            # しようとして`ValueError`になる実クラッシュを、実機確認
            # (uvicorn+mock provider)で発見した。
            return 0.0

        if field_type == "boolean":
            # FORGE-CONVERSATION-READY-001(2026-08-12)で発見した実バグの
            # 修正。上の"number"と**同じ種類**の見落としである: JSON
            # Schemaの"boolean"を判定する分岐が無く、下のデフォルト分岐
            # (文字列"mock_result"を返す)へ落ちていた。呼び出し側が
            # `bool(...)`で変換すると、**空でない文字列は常にTrue**に
            # なるため、「Mockでは常にフラグが立つ」という危険な挙動に
            # なっていた——実際、`ConversationEngine`の
            # `external_effect`/`destructive`が常にTrueになり、mock
            # providerでの会話が**毎回CONFIRMへ倒れる**という形で
            # テストが検出した。
            #
            # 既定を`False`にしているのは、この2フィールドに限らず
            # 一般に「Mockは特別な状態を主張しない」のが安全側であるため
            # (フラグが立つ側を既定にすると、Mock利用時だけ通らない経路が
            # 生まれる)。
            return False

        if field_type == "object":
            return {}

        # --- Realistic Mock(FORGE-HANDOFF-LOCAL-AI-UX-004 §35)---------
        # ユーザーの実際の発話から、もっともらしい日本語を組み立てる。
        # 以前はこれらが全て`"mock_result"`になっており、生成された
        # Toolのタイトルや会話文へそのまま露出していた(実機で確認)。
        utterance = _extract_user_utterance(prompt)
        if utterance:
            topic = _topic_of(utterance)
            if name == "problem":
                return utterance
            if name == "build_brief":
                return f"{topic}を記録・管理するための道具。思いついた時に追加して、あとから見返せる。"
            if name == "question":
                # Mockは本当の意味で「聞くべきこと」を判断できない。
                # ただし空文字を返すとEngineが質問なしと解釈するため、
                # 会話として成立する一般的な確認文を返す。
                return f"{topic}について、自分だけで使う感じですか？"
            # 名前として使われるフィールドは、説明文ではなく**短い名詞句**を
            # 返す(`_title_for`参照)。話題キーワードの照合は`example_items`
            # と同様にプロンプト全体に対して行う——compile段のプロンプトには
            # 生の発話が無く、`build_brief`経由でしか話題が現れないため。
            if name in ("entity_label", "app_title"):
                return _title_for(prompt, topic)
            if name in ("goal", "title", "purpose") and name not in labeled_values:
                return _title_for(prompt, topic)

        # デフォルトは文字列。フィールド名に応じて、多少意味のある値を返す。
        if name in ("goal", "title", "purpose"):
            # FORGE v0.2 Final Gate P3対応: 上流(Planner/Intent側)が既に
            # 決定した値がプロンプト内に存在する場合、それを**そのまま
            # 再利用する**(単語抽出で作り直さない)。これにより、
            # "compile" stageの"title"が"planning" stageで既に決定した
            # 妥当なtitleをそのまま維持できる(以前は単語抽出のやり直しで
            # 内部キー名が混入し破綻していた)。
            if name in labeled_values and labeled_values[name].strip():
                return labeled_values[name]
            return " ".join(words[:5]) if words else "mock_result"
        return "mock_result"


# 型チェック用の確認(実行時には意味を持たないが、各スタブが本当に
# LLMAdapter Protocolを満たす形になっているかを明示する)。
_PROVIDERS: tuple[LLMAdapter, ...] = (
    OpenAIProvider(),
    ClaudeProvider(),
    GeminiProvider(),
    OSSProvider(),
    ForgeAIProvider(),
    MockLLMAdapter(),
)
