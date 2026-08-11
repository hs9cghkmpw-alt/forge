# KNOWN ISSUES

Task003(FORGE-MERGE-001)時点。Prototype v0.1.3のKNOWN_ISSUES.mdの書式を踏襲する
(制約 / 今回は対応しない理由、を明記する)。

## ~~Dart/Flutterコードが`flutter analyze`未実施~~ → **解消済み(2026-08-11、FORGE-AI-QUALITY-001)**

**この制約は「サンドボックスの物理的制約」ではなかった。** CEO「出し惜しみせず、
完璧を求めてくれ」という指示を受けて改めて調査したところ、`storage.googleapis.com`
(Flutter公式のリリース配布元)がこの環境のプロキシ経由で到達可能であることが
判明した。実際にFlutter SDK(stable、3.44.9)をダウンロード・展開し、
`flutter pub get`・`flutter analyze`・`flutter test`をすべて実行できた
(`pub.dev`も到達可能だったため依存パッケージの解決にも成功した。一方
`github.com`・`pub.dartlang.org`はプロキシに拒否される)。

**セットアップ手順(次回セッションでの再現用、SDKはスクラッチパッド配下で
セッションをまたいで永続しないため毎回必要)**:
```bash
curl -sS -o flutter.tar.xz \
  "https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_3.44.9-stable.tar.xz"
tar -xf flutter.tar.xz
git config --global --add safe.directory "$(pwd)/flutter"
git config --global --add safe.directory /home/user/forge
export PATH="$(pwd)/flutter/bin:$PATH"
cd /home/user/forge/frontend && flutter pub get && flutter analyze && flutter test
```
(最新の安定版URLは`https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json`
の`current_release.stable`から辿った`releases[].archive`で確認できる。)

**この発見が意味すること**: これまで「Flutter SDK不在のため未検証」として
記録されてきたDart/Flutter側の実装(TD25の音声入力、TD30のローカル永続化、
TD34/TD36のWidget追加等)は、いずれも一度も実際に検証されていなかった。
実際に検証した結果、**4種類の新規Widget(choice_field/bar_chart/date_field/
tab_view)が、`widget_registry_core.dart`の`typeNameOf()`という網羅的switch式に
ケースを追加し忘れていたため、一度もRuntime上で描画できない状態だった**
という重大な実バグが見つかった(TD37に詳細を記録)。加えて、既存の
Dart単体テスト・Widget Test・E2E Testを実際に実行した結果、3件の
(このセッションの作業とは無関係な、より以前のUIリデザインに起因する)
既存テストの不整合も発見・修正した。全435件のDart/Flutterテストが
現在通過することを確認済み(2026-08-11時点)。

## Backend(FastAPI/Pydantic)コードが未実行
制約: pydantic/fastapiがClaudeのサンドボックスに無く、ネットワーク不可のためインストールできない。
今回は対応しない理由: 上記と同じ。呼び出される側の純粋関数(mock_generator.py・
schema_validator.py)は`python -m unittest`で26/26件検証済み。ルーター層(HTTPの皮)のみ未検証。

## `ruff check`未実行
制約: ruffがClaudeのサンドボックスに無い。
今回は対応しない理由: 上記と同じ。`py_compile`による構文チェックのみ実施(全ファイル合格)。
Lintルール違反(未使用import等)が無い保証はない。

## GitHub Actions上でのCI実行が未確認
制約: Claudeにgit/GitHub操作の手段が無い。
今回は対応しない理由: CEOが最初のPR/pushを行った時点で初めて確認できる。

## 生成アイテムのIDにタイムスタンプを使っている
制約: `ForgeRuntimeState.addChecklistItem`は`DateTime.now().microsecondsSinceEpoch`を
IDに使っており、理論上は同一マイクロ秒での連続追加で衝突しうる(実際には人間の操作速度では
起こらない)。
今回は対応しない理由: 縦の一本の完成を優先。衝突検知が必要になったらUUID等へ切り替える。

## AI生成アプリの状態はアプリ再起動で消える → **ローカル保存分は解消済み(2026-08-11、未検証)**
制約: `ForgeRuntimeState`はメモリ内のみで、永続化していない
(Backendの`apps`/`app_versions`テーブルは未着手。ROADMAP.md Phase 3参照)。
今回は対応しない理由: 縦の一本のスコープ外。永続化はPhase 3の残タスク。

**2026-08-11追記(FORGE-AI-QUALITY-001)**: CEO「これを、ほんとにアプリストアで
人気レベルのアプリをつくれるようなクオリティにするにはどうしたらいい？」を
受けて実施した調査で、この項目こそが「app store品質」への最大の障壁である
ことを確認した(生成したチェックリスト・家計簿等のアプリが、閉じるたびに
入力内容ごと消える設計では、実用アプリとして成立しない)。

ROADMAP.mdが元々想定していた「Backendの`apps`/`app_versions`テーブル+
Supabase」という**サーバー側・マルチデバイス同期**の永続化は、Supabase
アカウント作成等CEO側の作業が必要なため今回は着手できなかった。代わりに、
既に`SavedForgeApp`(アプリ定義)の保存に使っている`shared_preferences`
(ローカル端末内のみの永続化)を、**実行時State(ユーザーが実際に追加した
チェックリスト項目・家計簿の記録等)**にも拡張して適用した。

* `ForgeStateValue`(`forge_document.dart`)へ`toJson()`を追加し、
  `fromJson()`と対称な変換を可能にした。
* `mergePersistedState()`: 文書の初期値へ、保存済みの実行時Stateを
  安全にマージする(型不一致・破損データは黙って無視し、初期値へ
  フォールバックする)。
* `AppLibraryRepository`へ`loadRuntimeState`/`saveRuntimeStateForScreen`/
  `deleteRuntimeState`を追加(既存の`shared_preferences`実装を拡張)。
* `ForgeScreenView`が`ForgeRuntimeState`の変化(`notifyListeners`)を
  検知するたびに自動保存する(text_fieldの1文字ごとの入力は`notify:
  false`のため対象外、既存の挙動を活用)。
* My Apps・ホーム画面の「最近のアプリ」・履歴・生成直後のプレビューの
  計4箇所を配線した。

**未解決のまま残る点**: サーバー側保存・マルチデバイス同期は依然未着手
(引き続きROADMAP.md Phase 3の課題)。ローカル1台のみでの永続化。

**Claude環境での検証状況(正直な申告)**: この作業環境にDart/Flutter SDKが
無いため、**一切実行できていない**(構文の目視レビュー・括弧バランスの
機械チェックのみ実施)。新規Unit Test 2ファイル(`forge_state_persistence_
test.dart`・`shared_preferences_app_library_repository_test.dart`、
Widget Pumpingを伴わない純粋なDartロジックのテストのため、他のUI変更より
実行時に問題が出るリスクは低いと考えている)を追加したが、これも未実行。
CEO環境で`flutter test`を実行し、結果を共有してほしい。

## Repair Engineが無い
制約: Validatorが不合格を返した場合、現状は「生成失敗」としてユーザーへ即座にエラー表示するのみ。
今回は対応しない理由: FORGE-MERGE-001の優先順位(21章)でRepair Engineは縦の一本より後段。
Mock Generatorは設計上ほぼ必ずValidatorへ合格する(26/26件のテストで確認済み)ため、
現時点での実害は小さい。

## Androidエミュレータからの接続先
制約: `frontend/lib/core/network/dio_client.dart`の`kForgeApiBaseUrl`は`http://localhost:8000`
固定。Androidエミュレータからは`localhost`で自PCのBackendに届かない。
今回は対応しない理由: `.env`/`core/config`が無いため設定の外出しはPhase 0の残タスク
(ROADMAP.md参照)。検証手順にエミュレータ向けの値(`10.0.2.2`)を明記して回避する。
