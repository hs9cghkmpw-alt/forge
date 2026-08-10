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

## AI生成アプリの状態はアプリ再起動で消える
制約: `ForgeRuntimeState`はメモリ内のみで、永続化していない
(Backendの`apps`/`app_versions`テーブルは未着手。ROADMAP.md Phase 3参照)。
今回は対応しない理由: 縦の一本のスコープ外。永続化はPhase 3の残タスク。

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
