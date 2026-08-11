# iPhoneで動かすためのセットアップ(未検証、CEO環境での実施が必須)

**先に知っておいてほしいこと**: この作業環境(Claude)にはFlutter SDK自体が
無く、`flutter create`のような実際のツール実行が一切できません。この
ガイドは、既存コード(`pubspec.yaml`・`speech_to_text`パッケージの公式
ドキュメント等)から分かる範囲で「何をすればよいか」をまとめたものであり、
**Claudeが実際に試して確認した手順ではありません**。CEO環境(Mac)で
実施し、うまくいかない箇所があれば教えてください。

**前提条件**: iOS向けのビルドには**Mac**が必須です(XcodeがmacOS専用の
ため)。Windows/Linuxでは実施できません。

---

## 0. 今の状態

このリポジトリには、まだ`frontend/ios/`フォルダが一度も作られていません
(`frontend/web/`のみ存在)。iPhoneで動かすには、まずこのフォルダを
生成する必要があります。

---

## 1. 事前に準備するもの

| 必要なもの | 備考 |
|---|---|
| Mac | Xcodeを動かすため必須 |
| Xcode | App Storeから無料インストール(数十分〜数時間かかることがあります) |
| Apple ID | 実機(あなたのiPhone)で動かすための署名に必要(無料のApple IDで可、有料のApple Developer Programは今回は不要) |
| iPhone本体 + Lightning/USB-Cケーブル | 実機テスト用(Xcode Simulatorだけならケーブル不要) |
| Flutter SDK | 既にBackend/Frontendのセットアップ(`GETTING_STARTED.md`)で導入済みの前提 |

---

## 2. iOS向けの設定一式を生成する

`frontend/`フォルダで以下を実行します。

```bash
cd forge/frontend
flutter create --platforms=ios .
```

**なぜ`--platforms=ios`を付けるか**: 何も指定しないと`android`等も
まとめて生成されます。今回はiPhoneのみが目的なので範囲を絞っています
(Androidも後で欲しくなったら`--platforms=android`で追加できます)。

成功すると`frontend/ios/`フォルダが新しくできます。既存の`lib/`・
`pubspec.yaml`等は変更されません。

---

## 3. マイク機能(音声入力)向けの設定を追加する

このアプリは`speech_to_text`パッケージを使ってマイクボタンを実装して
います(`TECH_DEBT.md` TD25参照、これも未検証の機能です)。iOSでは、
マイク・音声認識を使う理由をユーザーに説明する文言を`Info.plist`へ
**明示的に書かないと、アプリがクラッシュするか、AppleのApp Store審査で
却下されます**(iOSの仕様)。

`frontend/ios/Runner/Info.plist`を開き、`<dict>`タグの内側に以下を
追加してください。

```xml
<key>NSMicrophoneUsageDescription</key>
<string>音声でアプリの内容を入力するためにマイクを使用します。</string>
<key>NSSpeechRecognitionUsageDescription</key>
<string>話した内容をテキストに変換するために音声認識を使用します。</string>
```

(文言はそのままでも構いませんし、CEOの言葉で書き直しても構いません。
ユーザーに表示される説明文なので、自然な日本語であれば問題ありません。)

---

## 4. Xcode Simulatorで動かしてみる(実機不要、まず試すのにおすすめ)

```bash
open -a Simulator
flutter run
```

`flutter run`が複数の起動先(Chrome・Simulator等)を検出した場合、
どれを使うか聞かれます。iPhoneのSimulatorを選んでください。

---

## 5. 実機(あなたのiPhone)で動かす

1. iPhoneをMacへケーブルで接続します。
2. iPhone側で「このコンピュータを信頼しますか？」と聞かれたら「信頼」を
   選びます。
3. Xcodeで`frontend/ios/Runner.xcworkspace`を開きます
   (`Runner.xcodeproj`ではなく`.xcworkspace`の方を開くこと)。
4. 左側の「Runner」プロジェクト → 「Signing & Capabilities」タブで、
   「Team」にあなたのApple IDを設定します(初回はXcode →
   Settings → Accounts からApple IDを追加する必要があります)。
5. 画面上部の実行先を、接続したあなたのiPhoneに切り替えます。
6. ターミナルに戻り、以下を実行します。

   ```bash
   flutter run
   ```

7. 初回はiPhone側で「信頼されていないデベロッパ」という警告が出ます。
   iPhoneの「設定」→「一般」→「VPNとデバイス管理」から、使用した
   Apple IDのプロファイルを信頼する操作が必要です(無料のApple IDで
   ビルドしたアプリは、7日ごとに再インストール・再信頼が必要になる
   という制限があります。これはApple側の仕様であり、Forge固有の問題
   ではありません)。

---

## 6. Backendへの接続について

iPhone実機は`localhost`では動きません(iPhone自身から見た
`localhost`はiPhone自身を指してしまうため)。パソコン側のBackendへ
繋ぐには、パソコンのLAN内IPアドレスを指定する必要があります。

```bash
flutter run --dart-define=FORGE_API_BASE_URL=http://(パソコンのIPアドレス):8000
```

パソコンとiPhoneが同じWi-Fiに接続されている必要があります。

---

## 7. うまくいかないときは

| 症状 | 考えられる原因と対処 |
|---|---|
| `flutter create --platforms=ios .`が失敗する | Xcodeが正しくインストールされているか(`xcode-select --install`実行済みか)確認してください。 |
| マイクボタンを押しても反応しない・クラッシュする | 3章のInfo.plist設定を忘れていないか確認してください。 |
| 「信頼されていないデベロッパ」から進めない | 5章の手順7を参照してください。 |
| iPhoneからBackendに繋がらない | 6章参照。パソコンとiPhoneが同じWi-Fiか、Backendのファイアウォール設定(パソコン側)を確認してください。 |
| そもそも`flutter create`で何が起きるか不安 | 既存の`lib/`・`pubspec.yaml`等は変更されません。新規に`ios/`フォルダが追加されるだけです。心配であれば、実行前に`git status`で作業ツリーが綺麗な状態か確認し、`git add ios/ && git commit`で一旦区切りをつけてから進めると安全です。 |

---

## 8. その先(App Storeへ公開したい場合)

今回のガイドは「自分のiPhoneで動かして試す」までを対象にしています。
実際にApp Storeへ公開するには、別途以下が必要になります(今回は
スコープ外)。

- 有料のApple Developer Program(年額)への登録
- アプリアイコン・スクリーンショット・プライバシーポリシーの用意
- App Store Connect側での審査申請
- プッシュ通知等を使う場合はさらに別途設定

これらは技術的な実装というより、Apple側の申請・審査プロセスが中心に
なるため、必要になったタイミングで別途相談してください。
