# 追加Cloud Providerの配線検証 — 受け取ったキーの扱いを含む

**2026-08-17 / branch `claude/forge-master-handoff-k46jns` / TD67**

---

## 0. 結論（1行）

**コード変更は不要だった。** 設定4行で載ることを、実際にHTTPを走らせて
確認した。ただし**実APIは1回も呼べていない**（この環境はegress禁止）。

---

## 1. 受け取ったキーの扱い

CEOからチャットで**OpenAIのAPIキー**を受け取った。

### 保存していない

`CLAUDE.md` §4 は「Git追跡対象に持ってよいのは環境変数の**名前**だけ。
値は持たない / Source・Test Fixture・Documentation・Reportへ実値を
書かない / ログにも出さない。長さや先頭数文字も出さない」と定めている。

したがって**リポジトリにも、この作業環境の`backend/.env`にも書いて
いない**。疎通確認に使った一時ファイルは、使用後に削除した。

このドキュメントを含め、値はどこにも書いていない。

### それでも失効が必要である

**チャットに平文で流れたので、会話ログに残っている。** 保存しなかった
ことと、露出しなかったことは違う。CEOへ失効（rotate）を依頼した。

### これは「無料枠の追加」ではない

依頼していたのは Groq / Cerebras / OpenRouter の**無料枠**だった。
OpenAIのAPIは**前払いクレジット制で無料枠が無い**。クレジットが
無ければ`429 insufficient_quota`で1回も呼べず、あれば**有料**で動く。

元の問題（Geminiの1日20回/Modelでは検証だけで尽きる、TD66）に対して
**有料での解決になる**ことを、HANDOFFに明記した。判断はCEOのもので
あり、こちらで勝手に「解決した」とはしない。

---

## 2. 実APIを呼べなかった事実

```
実施 : GET https://api.openai.com/v1/models （Authorizationヘッダ付き）
結果 : HTTP 000 / curl: (56) CONNECT tunnel failed, response 403
```

この開発セッションのegressポリシーによる遮断である。環境のドキュメント
（`/root/.ccr/README.md`）は

> 403 / 407 from the proxy … Do not retry or route around it — report the
> blocked host.

としているので、**回避していない**。

したがって**キーが有効かどうかは分からない**。これはキーの問題ではなく、
ここから外へ出られないという問題である。混同しないよう区別して報告した。

---

## 3. 代わりに検証したこと: Forge側の配線

実APIが呼べないなら、**Forge側だけでも確かめられることを確かめる**。

localhostにOpenAI互換の偽エンドポイントを立て、Registry → 環境変数の
解決 → Adapter → 実際のHTTPリクエスト、までを通した。

### 確認できたこと（実測）

```
provider_name : test_openai_compatible      ← FORGE_EXTRA_PROVIDERS が拾った
model         : some-model                  ← FORGE_<ID>_MODEL から解決
base_url      : http://127.0.0.1:xxxxx/v1   ← FORGE_<ID>_BASE_URL から解決

偽サーバが受け取ったもの:
  path          : /v1/chat/completions      ← OpenAI互換の正しいパス
  Authorization : Bearer <環境変数の値>      ← 認証方式も正しい
  model         : some-model                 ← 指定modelを送っている
  body          : messages / model / response_format / stream / temperature
```

`complete_structured()` が偽の応答を正しくdictへ戻すところまで通った。

### コード変更は1行も無い

`FORGE_EXTRA_PROVIDERS` は元からある口である（010の`cloud`という
「中身が入れ替わりうる汎用名」を廃し、**provider_idを名指しさせる**
形にしたもの）。011 §1「Protocol駆動でAdapterを共有する。Providerが
増えても**HTTP実装は増えない**」という主張が、実際に効いていることの
確認にもなった。

### 回帰テストとして残した

`backend/tests/test_extra_cloud_provider.py`（7件）。使い捨ての
シェル実験にすると次のセッションで消える（`CLAUDE.md` §1）。

**配線破壊試験3件**（外すと落ちることを確認済み）:

| 外したもの | 落ちたテスト |
|---|---|
| `FORGE_EXTRA_PROVIDERS`が追加Providerを載せない | 2 |
| 予約語チェック（既存Provider名の乗っ取り防止） | 1 |
| `required_env`（設定が欠けたProviderを候補から外す） | 1 |

---

## 4. 検証区分

**混同しないよう正確に分ける。**

| 項目 | 区分 |
|---|---|
| 追加Providerが設定だけで載ること | **実測** |
| 環境変数からbase_url/model/keyが解決されること | **実測** |
| OpenAI互換のHTTPを正しい形で送ること | **実測（Test Double）** |
| 設定が欠けたProviderを候補にしないこと | **実測** |
| 既存provider_idを上書きできないこと | **実測** |
| **実際のOpenAI APIが応答すること** | **未検証**（egress禁止で1回も呼べていない） |
| **受け取ったキーが有効であること** | **未検証**（同上） |
| **構造化出力の形式差・エラー本文の違い** | **未検証**（実接続でしか分からない） |

TD67（第二Cloudが実API未検証）は**半分だけ**解消した。

---

## 5. CEOのPCでの設定

```
FORGE_EXTRA_PROVIDERS=openai_platform
FORGE_OPENAI_PLATFORM_BASE_URL=https://api.openai.com/v1
FORGE_OPENAI_PLATFORM_API_KEY=（失効・再発行した新しい鍵）
FORGE_OPENAI_PLATFORM_MODEL=（コンソールで使えるモデル名）
```

**`BASE_URL`と`MODEL`は確認していない。** ここからOpenAIの公式
ドキュメントへ到達できないため、記憶から書いている。過去に同じ理由で
「公称値をコードへ固定しない」という判断をしており（`_openai_compatible_cloud`
のコメント参照）、ここでも定数としてコードへは入れていない。
**コンソールの表示で確かめること。** 違っていればこの2行を直すだけで、
コードは触らない。

---

## 6. 自己監査（PRODUCT-DIRECTION §8）

1. **実測と公称を分けたか** — §4に区分表。実APIは**未検証**と明記
2. **Secretを持ち込んでいないか** — リポジトリにも`.env`にも書かず、
   一時ファイルは削除。長さも先頭数文字も出していない
3. **問題を黙って回避していないか** — egress 403は回避せず報告した
4. **依頼の前提が崩れたとき、黙って目標を変えていないか** — 「OpenAIは
   無料枠ではない」ことを、解決したと言わずに正面から報告した
5. **本番から呼ばれない仕組みを作っていないか** — 配線破壊試験3件
6. **報告を文書に残したか** — このファイル + HANDOFF + CHANGELOG +
   TECH_DEBT(TD67) + STATUS
