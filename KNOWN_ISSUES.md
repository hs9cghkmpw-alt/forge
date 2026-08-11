# KNOWN ISSUES

Task003(FORGE-MERGE-001)時点。Prototype v0.1.3のKNOWN_ISSUES.mdの書式を踏襲する
(制約 / 今回は対応しない理由、を明記する)。

## Dart/Flutterコードが`flutter analyze`未実施
制約: Claudeのサンドボックスに Dart/Flutter SDK が無く、ネットワークも無いため導入できない。
今回は対応しない理由: 対応できない(環境の物理的制約)。代わりに、相対import 23件の解決確認・
カスタム型の定義-参照突合という機械チェックを実施し、レビュー中に発見した2件の実装ミス
(未定義メソッド参照、switch文のフォールスルー)は修正済み。CEO環境での`flutter analyze`
実行が次の必須ステップ(Immediate Next Task参照)。

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
