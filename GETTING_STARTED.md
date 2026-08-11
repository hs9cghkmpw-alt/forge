# はじめての人向け セットアップガイド

このガイドは、**このリポジトリを一度も触ったことがない人**が、
GitHubからコードを取得して、実際にForgeを動かすところまでを
1つずつ説明します。

**先に知っておいてほしいこと**: このガイドのBackend(Python)の手順は、
Claude(このガイドを書いたAI)が実際にこの環境で実行し、動くことを
確認しています。一方、Frontend(Flutter)の手順は、Claudeの作業環境に
Flutter SDKが無いため、**一度も実行できていません**(内容は既存コードの
コメント・READMEの記述をもとに書いていますが、実際にコマンドを打って
確認したのはあなたが最初になります)。うまくいかない箇所があれば、
その内容を教えてもらえれば修正します。

---

## 0. 全体像

Forgeは2つの部分でできています。

- **Backend**(Python / FastAPI): 「アプリを作って」という文章を受け取り、
  画面の設計図(JSON)を作って返すサーバー。
- **Frontend**(Flutter): その設計図(JSON)を実際の画面として描画する
  アプリ本体。ブラウザ(Chrome)上でも動かせます。

**Frontendは、既定でBackendに接続しようとします**(後述)。そのため、
先にBackendを起動してから、Frontendを起動する順番がおすすめです。

---

## 1. 事前に準備するもの

| 必要なもの | バージョン目安 | 確認コマンド |
|---|---|---|
| Git | 何でも可 | `git --version` |
| Python | 3.11以上 | `python3 --version` |
| Flutter SDK | 3.3以上(`pubspec.yaml`の`environment.sdk`参照) | `flutter --version` |
| GitHubへのアクセス権 | このリポジトリ(`hs9cghkmpw-alt/forge`)を読める権限 | - |

Flutterがまだ入っていない場合は、公式サイトの手順に従ってインストール
してください: https://docs.flutter.dev/get-started/install

---

## 2. リポジトリを取得する(GitHubから)

ターミナル(Windowsの場合はPowerShellでも可)を開いて、作業したい
フォルダで以下を実行します。

```bash
git clone https://github.com/hs9cghkmpw-alt/forge.git
cd forge
git checkout claude/forge-master-handoff-k46jns
```

**なぜ`git checkout`が必要か**: 2026-08-10時点で、このリポジトリには
`claude/forge-master-handoff-k46jns`というブランチしか存在しません
(まだ`main`ブランチが作られていません)。`git clone`した直後は
このブランチに自動的にいる場合もありますが、念のため上記コマンドで
明示的に切り替えておくと安全です。

---

## 3. Backendを起動する(Python / FastAPI)

### 3.1 仮想環境を作る

```bash
cd backend
python3 -m venv .venv
```

仮想環境を有効化します(OSによってコマンドが違います)。

```bash
# macOS / Linux
source .venv/bin/activate

# Windows(PowerShell)
.venv\Scripts\Activate.ps1

# Windows(コマンドプロンプト)
.venv\Scripts\activate.bat
```

ターミナルの行頭に`(.venv)`と表示されれば成功です。

### 3.2 必要なパッケージをインストールする

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.3 テストを実行して、正しくインストールできたか確認する

```bash
python -m pytest -q
```

`962 passed, 12 skipped`(2026-08-11時点でClaudeが実際に確認した数値。
作業が進むたびに件数は増えます)のように、`passed`件数が多数出て、
`failed`が無ければ成功です。

### 3.4 サーバーを起動する

```bash
uvicorn app.main:app --reload
```

以下のような表示が出れば起動成功です。

```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**このターミナルは閉じずに、起動したままにしておいてください。**
Frontendを動かす間、Backendはずっと起動している必要があります。

### 3.5 起動確認(ブラウザ or 別ターミナルから)

ブラウザで以下のURLを開くか、

```
http://127.0.0.1:8000/health
```

別のターミナルで以下を実行します。

```bash
curl http://127.0.0.1:8000/health
```

`{"status":"ok"}`と返ってくれば、Backendは正常に起動しています。

### 3.6 (任意)本物のAI(Gemini)に繋いでみる

**既定では、AI生成は`mock`(決定的なキーワードマッチング、本物のAIでは
ない)を使います。** 本物のAI(Google Gemini、無料枠あり)に繋ぎたい場合は、
以下の手順で設定します。

1. https://aistudio.google.com/apikey にアクセスし(Googleアカウントが
   必要)、「Get API key」からAPIキーを取得します。
2. `backend/.env.example`を`backend/.env`という名前でコピーします。
3. `backend/.env`を開き、`GEMINI_API_KEY=`の後ろに取得したキーを貼り付けます。
4. Backendを再起動します(3.4に戻って`uvicorn`をCtrl+Cで止めて、
   もう一度起動)。

**注意**: `GEMINI_API_KEY`を設定しただけでは、既定の動作は変わりません
(既定は引き続き`mock`)。実際にGeminiを使うには、リクエストで
`generation_options.provider: "gemini"`を明示的に指定する必要があります
(6章のcurl例を参照)。**現時点で、Flutterアプリ側にはGeminiを選ぶUIが
まだ無く**、`curl`等でAPIを直接呼ぶ場合のみGeminiを試せます。

**2026-08-10追記: 実機確認済みです。** CEOが共有した実際のAPIキーで、
このセッション内で実際にGemini APIへ接続し、`買い物リストを作って`
`旅行の持ち物チェックリストを作って`が実際にForge Language準拠のJSON
として生成されることを確認しました(既定モデルは試行錯誤の末
`gemini-flash-latest`にしています。詳細は`TECH_DEBT.md` TD15参照)。
あなたが試す際は、上記手順どおりでそのまま動くはずです。うまくいかない
場合はエラーメッセージを教えてください。

---

## 4. Frontendを起動する(Flutter)

**ここから先は、Claude環境では実行できていません**(1章参照)。

Backendを起動したまま、**別のターミナル**を新しく開きます。

```bash
cd forge/frontend       # リポジトリのfrontendフォルダへ
flutter pub get
flutter run -d chrome
```

数十秒〜数分待つと、Chromeが自動的に開き、Forgeのホーム画面が
表示されます。

**2026-08-11追記(音声入力、未検証)**: ホーム画面の入力欄の横に
マイクボタンが追加されました(`speech_to_text`パッケージ)。この機能は
Claude環境では一切実行できておらず、`flutter pub get`の依存解決から
未確認です。`flutter pub get`が失敗した場合、または`flutter run`時に
音声入力関連のコンパイルエラーが出た場合は、エラーメッセージをそのまま
教えてください(`TECH_DEBT.md` TD25参照)。このアプリは`android/`・
`ios/`フォルダを生成していないため、音声入力はWeb(Chrome)専用です。

**2026-08-11追記(生成アプリのローカル保存、未検証)**: 「マイアプリ」・
ホーム画面の「最近のアプリ」・履歴から開いたアプリで、チェックリストの
追加・家計簿の記録等が、アプリを閉じても次回開いたときに残るように
なりました(以前はアプリを閉じるたびに消えていました。`KNOWN_ISSUES.md`
「AI生成アプリの状態はアプリ再起動で消える」参照)。この機能もClaude
環境では一切実行できていません。試す際は、①何かアプリを生成して
「保存してあとで見る」を選ぶ、②チェックリストに項目をいくつか追加する、
③アプリを閉じてブラウザを再読み込みする、④「マイアプリ」からもう一度
開く、という手順で、追加した項目が残っているか確認してください。
うまく残らない場合や、コンパイルエラーが出た場合は、エラーメッセージを
そのまま教えてください(`TECH_DEBT.md` TD30参照)。

**接続モードについて(重要)**: このアプリは既定で「Live Mode」
(実際にBackendのAPIを呼ぶモード)で起動します(以前は既定で
Mock Modeでしたが、`frontend/lib/core/config/app_config.dart`の
コメントにあるとおり、既定値が変更されています)。そのため、
**Backend(3章)を先に起動していないと、アプリを使おうとしたときに
「接続できませんでした」というエラーになります。**

もしBackend無しで、AIを使わない決定的なMockだけで動作を見たい場合は、
以下のように起動します。

```bash
flutter run -d chrome --dart-define=USE_MOCK_GENERATION=true
```

Backendの接続先を変えたい場合(例: 別のポートで起動した場合)は、
以下のように指定します。

```bash
flutter run -d chrome --dart-define=FORGE_API_BASE_URL=http://127.0.0.1:8000
```

---

## 5. 実際に使ってみる

1. ホーム画面の入力欄に、作りたいアプリを日本語で入力します。
   例:「買い物リストを作って」
2. 送信ボタン(円形の矢印アイコン)を押します。
3. 数秒待つと、生成中画面(チェックリスト形式の演出)を経て、
   完成画面が表示されます。
4. 「アプリを開く」を押すと、実際に生成されたアプリを操作できます。

**2026-08-11追記(試してみてほしい例)**: `provider: "gemini"`を指定した
状態(3.6参照)で、以下のような入力も試してみてください。

- 「満足度アンケートを作って」→ 以前はチェックリスト形式になって
  いましたが、今は実際の質問文が複数の入力欄に分かれた、本物の
  アンケートフォーム(送信すると「送信完了」画面へ遷移)になります
  (`TECH_DEBT.md` TD29参照)。
- 「買い物リストを作って」→ 以前は「牛乳・卵・パン」という固定の
  例文でしたが、今はGeminiが依頼内容に応じた具体的な初期データを
  提案します(`TECH_DEBT.md` TD26参照)。
- 何かアプリを保存して、チェックリストに項目を追加したあと、
  一度ブラウザを閉じて(またはタブを再読み込みして)「マイアプリ」
  から再度開いてみてください。追加した項目が残っていれば、
  ローカル保存機能(`TECH_DEBT.md` TD30、**未検証**)が正しく
  動いています。うまく残らない場合は、そのままエラー内容を教えて
  ください。

---

## 6. (任意)APIだけを直接試す

Flutterを使わず、Backendが正しく動いているかだけを確認したい場合は、
`curl`で直接APIを呼び出せます(Backendを起動した状態で、別ターミナルから)。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ai/generate \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.0",
    "input": {
      "natural_language": "買い物リストを作って"
    }
  }'
```

Forgeの画面設計図(JSON)がそのまま返ってくれば、Backendは正常に動作しています。

### 6.1 本物のAI(Gemini)を試す場合

3.6で`GEMINI_API_KEY`を設定済みなら、`generation_options`で明示的に
`gemini`を指定すると、実際にGemini APIを呼びます。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ai/generate \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.0",
    "input": {
      "natural_language": "買い物リストを作って",
      "generation_options": {
        "engine": "forge_ai",
        "provider": "gemini"
      }
    }
  }'
```

`GEMINI_API_KEY`が未設定、またはGemini API側でエラーが起きた場合は、
`status: "error"`とエラー内容が返ります(そのままの内容を教えてもらえれば
調査します)。

---

## 7. うまくいかないときは

| 症状 | 考えられる原因と対処 |
|---|---|
| `pip install -r requirements.txt`が失敗する | Pythonのバージョンを確認してください(3.11推奨)。それでも失敗する場合は、エラーメッセージを教えてください。 |
| `uvicorn`コマンドが見つからない | 仮想環境(`.venv`)を有効化し忘れている可能性があります。3.1に戻って`source .venv/bin/activate`(またはWindows版)を実行してください。 |
| Frontendが「接続できませんでした」と表示する | Backend(3章)が起動していない可能性が高いです。Backendのターミナルが動いたままか確認してください。 |
| `flutter run -d chrome`で`No devices found`と出る | `flutter devices`でChromeが認識されているか確認してください。Chromeがインストールされていない場合はインストールが必要です。 |
| Gemini呼び出しが`GEMINI_API_KEY`エラーになる | `backend/.env`にキーを書いた後、Backend(uvicorn)を再起動しましたか？環境変数は起動時にしか読まれません。 |
| Gemini呼び出しが403/429エラーになる | 無料枠の制限(利用回数・レート制限)に達した可能性があります。少し時間を置くか、Google AI Studioでキーの状態を確認してください。 |
| `flutter pub get`や`flutter run`でエラーが出る | このガイドのFlutter部分はClaude環境で未検証です。エラーメッセージをそのまま教えてもらえれば、次のセッションで調査・修正します。 |
| Androidエミュレータから繋がらない | `localhost`ではなく`10.0.2.2`を使う必要があります(`app_config.dart`のコメント参照)。`--dart-define=FORGE_API_BASE_URL=http://10.0.2.2:8000`を試してください。 |

---

## 8. もっと詳しく知りたくなったら

- [README.md](./README.md): プロジェクト全体の概要・技術構成・ディレクトリ構造
- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md): アーキテクチャ全体設計
- [CHANGELOG.md](./CHANGELOG.md): これまでの変更履歴(Taskごと)
- [TECH_DEBT.md](./TECH_DEBT.md): 既知の技術的負債
- [KNOWN_ISSUES.md](./KNOWN_ISSUES.md): 今すぐ困りうる制約(未検証項目等)
- [2026-08-11-SESSION-REVIEW-SUMMARY.md](./2026-08-11-SESSION-REVIEW-SUMMARY.md):
  直近の作業内容まとめ(レビュー用)
- [docs/reports/](./docs/reports/): 各作業の実施レポート
