# 受け取ったAPIキーの扱いと、試験のやり方

**2026-08-17 / CEOの質問「さっきのAPIはどこかに使った？試験するならどうやる？」への回答**

---

## 1. 結論（先に3行）

1. **どこにも使っていません。** 送信も0回です（後述のとおり、接続そのものが
   遮断されたので鍵はネットワークへ出ていません）
2. **リポジトリにも `.env` にも書いていません。** 実際に検査した結果を §2 に載せます
3. **試験はCEOのPCでしかできません。** 手順を §4 に、コピーして貼るだけの形で書きました

---

## 2. 「どこかに使った？」— 検査した結果

記憶で答えず、実際に検査しました。

| 調べた場所 | 方法 | 結果 |
|---|---|---|
| リポジトリの全ファイル | `sk-` で始まる文字列を全文検索 | **該当なし** |
| Gitの全履歴（1998オブジェクト） | 全commitを走査 | **該当なし** |
| `backend/.env` | 変数名を列挙 | `GEMINI_API_KEY` と `FORGE_ENV` のみ。**鍵は入っていません** |
| 作業用の一時フォルダ | ファイル一覧 + 全文検索 | 使った一時ファイルは**削除済み**、該当なし |

> 検索に3件ヒットしましたが、いずれも第三者ライブラリ（`.venv` の中の
> ライセンス一覧）にある `sk-linking-protocols-exception` という
> **ライセンスID**でした。鍵とは無関係です。

### 鍵はネットワークにも出ていません

「疎通確認」として1回だけ `https://api.openai.com/v1/models` へ接続を
試みましたが、**接続の入口で遮断されました**。

```
curl: (56) CONNECT tunnel failed, response 403
```

これは技術的に重要です。HTTPSでは、

```
① まず CONNECT で「api.openai.com へ繋がせて」と頼む   ← ここで403で拒否された
② 繋がってから、暗号化された中で Authorization: Bearer <鍵> を送る  ← ここまで到達していない
```

という順序なので、**①で止まった＝鍵は一度も送信されていません**。
中継のプロキシが見たのは「api.openai.com へ繋ぎたい」という宛先だけです。

### それでも失効（作り直し）は必要です

**チャットの本文に平文で流れたため、会話ログに残っています。**
「保存しなかった」ことと「露出しなかった」ことは別です。

* OpenAIのコンソールで、この鍵を **Revoke（失効）**
* 新しい鍵を作成
* 新しい鍵は**チャットに貼らず**、CEOのPCの `backend/.env` へ直接書く

---

## 3. 試験の前に知っておいてほしいこと

**OpenAIのAPIには無料枠がありません。** 前払いのクレジット制です。

* クレジットあり → 動きます（**有料**。1回の生成でおよそ数円）
* クレジットなし → **1回も動きません**（`429 insufficient_quota`）

元の困りごと（Geminiの1日20回/Modelでは足りない）に対しては
**お金で解決する**形になります。無料で枠を増やしたい場合は
Groq / Cerebras / OpenRouter の取得を別途お願いします。設定手順は同じです。

---

## 4. 試験のやり方（CEOのPCで）

**3段階**に分けます。前の段が通らないと次に進む意味がありません。

### 段階0: 設定する

`backend/.env` に4行足します（既存の行は消さないでください）。

```
FORGE_EXTRA_PROVIDERS=openai_platform
FORGE_OPENAI_PLATFORM_BASE_URL=https://api.openai.com/v1
FORGE_OPENAI_PLATFORM_API_KEY=（作り直した新しい鍵）
FORGE_OPENAI_PLATFORM_MODEL=gpt-4o-mini
```

> **`BASE_URL` と `MODEL` は私が確認したものではありません。**
> この開発環境からOpenAIの公式ドキュメントへ到達できないため、記憶から
> 書いています。**コンソールの表示で確かめてください。** 違っていても
> この2行を直すだけで、コードは触りません。

---

### 段階1: 鍵が生きているか（Forgeを通さない）

**まずForgeを疑わない。** 鍵とネットワークだけを確かめます。

PowerShell（Windows）:

```powershell
$key = "（新しい鍵）"
curl.exe -s -o NUL -w "%{http_code}`n" -H "Authorization: Bearer $key" https://api.openai.com/v1/models
```

Mac / Linux:

```bash
read -s -p "key: " KEY; echo
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $KEY" https://api.openai.com/v1/models
```

**出た数字の読み方:**

| 出た数字 | 意味 | やること |
|---|---|---|
| `200` | **鍵は有効。段階2へ** | — |
| `401` | 鍵が違う / 失効している | コンソールで作り直す |
| `429` | 有効だが**クレジットが無い** | 課金を入れるか、Groq等へ切り替える |
| `000` | ネットワークに出られていない | 社内プロキシ・VPN・ファイアウォールを確認 |

---

### 段階2: Forgeが鍵を認識するか（APIは呼ばない）

**呼ばずに、設定が届いているかだけ**を見ます。ここは無料です。

```
cd backend
python -c "from dotenv import load_dotenv; load_dotenv('.env'); from app.ai.gateway.provider_registry import configured_providers, extra_provider_warnings; print('警告:', extra_provider_warnings()); print('使えるProvider:', [d.provider_id for d in configured_providers()])"
```

**期待する出力:**

```
警告: ()
使えるProvider: ['gemini', 'openai_platform', ...]
```

`openai_platform` が**出てこない**場合は、4行のどれかが欠けているか、
名前の綴りが違います。`警告:` に理由が出ることがあります。

---

### 段階3: 実際にAPIを呼ぶ（**ここで初めてお金/枠を使います**）

Forgeには実API用のテストが用意してあります。**普段は必ずSKIP**され、
`FORGE_LIVE_TEST=1` を付けたときだけ動きます。呼ぶ回数は**2回だけ**です。

PowerShell:

```powershell
cd backend
$env:FORGE_LIVE_TEST="1"; $env:FORGE_LIVE_PROVIDER="openai_platform"
python -m pytest tests/test_live_api.py -v
Remove-Item Env:FORGE_LIVE_TEST; Remove-Item Env:FORGE_LIVE_PROVIDER
```

Mac / Linux:

```bash
cd backend
FORGE_LIVE_TEST=1 FORGE_LIVE_PROVIDER=openai_platform python -m pytest tests/test_live_api.py -v
```

**`FORGE_LIVE_PROVIDER` で名前を指定するのが要点です。** これを付けないと、
既に設定済みのGeminiの方が先に選ばれ、**新しく足したOpenAIは一度も
叩かれません**（「動いた」と思って実は試せていない、という事故になります）。

**結果の読み方:**

| 出力 | 意味 |
|---|---|
| `passed` | **成功。実際に応答が返り、スキーマも満たしています** |
| `LiveProviderNotUsable` | 設定が足りない。メッセージに**欠けている変数名**が出ます |
| `insufficient_quota` を含むエラー | 鍵は有効だが**クレジットが無い** |
| `404` / `model` を含むエラー | `FORGE_OPENAI_PLATFORM_MODEL` の名前が違う |

---

### 段階4（任意）: 実際にアプリを1つ作ってみる

ここまで通れば、普段どおりアプリを作るだけで新しいProviderが使われます。
Geminiの枠が切れたとき、自動でこちらへ回ります。

---

## 5. 私の側で用意したもの

### 配線は確認済み（実APIなし）

localhostにOpenAI互換の偽サーバを立てて、**Forge側が正しい形でHTTPを
送ること**を確認しました。実APIは1回も呼んでいません。

```
送信先        : POST /v1/chat/completions   ← OpenAI互換の正しいパス
認証          : Authorization: Bearer <環境変数の値>
モデル名      : 設定したものがそのまま乗る
```

`backend/tests/test_extra_cloud_provider.py`（7件）として残してあります。

### 試験の入口にあった実バグを直しました

**この質問に答えようとして見つかりました。**

実APIテストがどのProviderを叩くかを決める部分が、`gemini` と `cloud` という
**固定の名前**を見ていました。ところが `cloud` という名前は 011 で廃止済み
です（「今日Groq・明日Cerebrasを同じ名前で受けると統計が混ざる」ため、
`groq` / `cerebras` … と分けた）。

つまり**第二のCloudをどれだけ正しく設定しても、実APIテストはGeminiしか
叩かず、新しいProviderは黙ってSKIPされていました。** 「設定したのに何も
起きない」という、原因の分からない無反応です。TD67（第二Cloudが実API
未検証）がずっと進まなかった一因でもあります。

直した内容:

* 固定の名前をやめ、**Registryが実際に持っているもの**から選ぶ
  （Providerが増えてもここを直す必要が無い＝直し忘れが起きない）
* `FORGE_LIVE_PROVIDER` で**狙って指定できる**ようにした
* 指定したProviderが叩けないときは**黙ってSKIPせず、欠けている変数名を
  挙げて失敗する**

さらに、**この誤りは実APIを呼ばないと分からない形**になっていたので、
鍵が無くても常時走る回帰テスト6件を足しました。旧実装へ戻すと3件が
落ちることを確認済みです。

---

## 6. 安全のルール（今後）

* 鍵の値を**チャットに貼らない**。`backend/.env` へ直接書く
  （`.env` はGitの追跡対象外です。確認済み: `.gitignore:18`）
* 鍵を渡す必要があるときは「置いた」とだけ伝えてください。値は不要です
* 一度チャットに出た鍵は**失効させる**
* CIにはAPIキーを置きません。実APIテストは既定でSKIPです

---

## 7. 検証区分

| 項目 | 区分 |
|---|---|
| 鍵がリポジトリ・履歴・`.env` に無いこと | **実測**（全文検索） |
| 鍵がネットワークへ出ていないこと | **実測**（CONNECT段階で403） |
| Forge側の配線がOpenAI互換HTTPを話すこと | **実測（Test Double）** |
| Live Testの Provider選択が設定を尊重すること | **実測**（配線破壊試験で確認） |
| **受け取った鍵が有効かどうか** | **未検証**（この環境から外へ出られない） |
| **実際のOpenAI APIの応答・エラー本文** | **未検証** |
