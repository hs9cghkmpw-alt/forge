# Forge が Chrome で実際に描画された証拠 — 2026-08-31

## 0. まず: これは**どのPCの結果か**

| | |
|---|---|
| Execution host | **Linux コンテナ**（Ubuntu 24.04.4 / kernel 6.18.44） |
| **ぱすとらる PC (Windows) の結果ではない** | Puro はこの環境に存在しない（`~/.puro` 無し） |
| Git SHA（この実行時点） | **`5cf6b6118ca54920db12c7b9c7e8d7f558fa3ef1`** |
| Branch | `claude/forge-master-handoff-k46jns`（clean / local == remote） |
| Flutter | 3.44.9 stable / Dart 3.12.2（`scratchpad/flutter_sdk`、**Puro 経由ではない**） |
| Browser | Chromium 141.0.7390.37（headless） |

`PHYSICAL-EXECUTION-CHECKPOINT-20260831.md` が記録した
**Puro のパス問題は、この host では再現できない**（Puro が無いため）。
したがってこの文書は**あちらのブロッカーを解決したものではない**。
「Forge が Chrome で描画されること」を**別の host で**証明したものである。

---

## 1. 実行したコマンド

```bash
export PATH="<scratchpad>/flutter_sdk/flutter/bin:$PATH"
export CHROME_EXECUTABLE="<scratchpad>/chrome-wrapper.sh"
flutter run -d chrome --no-web-resources-cdn \
    --web-port 8710 --web-hostname 127.0.0.1
```

`chrome-wrapper.sh` は Chromium に `--headless=new --no-sandbox
--disable-dev-shm-usage --disable-gpu` を足すだけの薄いラッパである。
**Forge 本体には一切触れていない**（環境側の修正のみ）。

## 2. 途中で分かった2つの原因

### (a) Chrome が見つからない

`flutter doctor` は `google-chrome` という名前を探すが、この環境にあるのは
Chromium である。`CHROME_EXECUTABLE` を指定すると device が現れる。

```
Chrome (web) • chrome • web-javascript • Chromium 141.0.7390.37
```

### (b) 起動はするが、真っ白になる

最初の実行では **`flutter run` 自体は成功していた**
（`Debug service listening on ws://127.0.0.1:...`）。
落ちていたのは**外向き通信**である。

```
Failed to load font Roboto at https://fonts.gstatic.com/...
Error: Failed to fetch dynamically imported module:
  https://www.gstatic.com/flutter-canvaskit/.../canvaskit.js
```

CanvasKit（描画エンジン）が CDN から取れないと engine が起動しない。
→ `--no-web-resources-cdn` で同梱物を使う。
フォントは撮影時にローカルの IPAGothic を差し替える
（**字形は製品の見た目ではない**——見てよいのは配置・重なり・階層）。

これは `scripts/capture_quality_gate_v2.py` が既に記録していた罠と同じで
ある。**「起動できない」ではなく「起動しているが何も写らない」**。

## 3. 結果

| 検査 | 結果 |
|---|---|
| `flutter run -d chrome` がアプリを起動 | **PASS**（`Debug service listening` / `Flutter run key commands`） |
| dev server が応答 | **PASS**（`http://127.0.0.1:8710/` → HTTP 200） |
| **Chrome 上で実際に Forge が描画** | **PASS**（画像を開いて目視確認済み） |
| **最低限の操作** | **PASS**（下記） |

### 実際に見えた画面（mobile 390x844）

`docs/visual-evidence/RUNTIME-CHROME-20260831/flutter-run-chrome-mobile-390x844.png`

- ヘッダ「Forge」ロゴ + **Mock** バッジ（AI 未接続であることを表示している）
- 見出し「最近、ちょっと困ってることある？」
- 説明文、入力欄、マイクボタン、送信ボタン
- 例のチップ4つ（家計簿 / ToDo / 日記 / 釣果記録）
- 「会話内容は安全に保護されます」
- ボトムナビ（ホーム / マイアプリ / 履歴）

### 実際に行った操作

`after-tap-suggestion-390x844.png`

「家計簿アプリを作りたい」のチップを**座標でタップ**した結果:

1. 入力欄に「家計簿アプリを作りたい」が入った
2. **送信ボタンが灰色から有効色（青紫）へ変わった**

押す前と後で画像が変わったことを機械的にも確認している
（変わらなければ FAIL として扱う）。

## 4. ログ

- `logs/forge-runtime-chrome-20260831.log`（`flutter run` の出力）
- 秘密情報は含まれない（API key / token / password の走査済み）

## 5. まだ言えないこと

- **ぱすとらる PC (Windows) の Puro 問題は未解決。** この host では再現不能
- ここで見たのは**ホーム画面と1操作**である。生成フロー全体の手動確認は未実施
- **Mock 表示**のとおり、実 AI には接続していない
