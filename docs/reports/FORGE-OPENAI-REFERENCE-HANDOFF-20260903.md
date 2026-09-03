# Forge OpenAI Reference Handoff — 2026-09-03

## 1. 現在地

OpenAI を Product Runtime の必須 Provider にせず、**Reference / Oracle Candidate（比較・校正用の基準候補）**として Forge に追加済み。

実装 commit:

- `f0eb5bb9a1fdbdcd27234bfa5638ace90942c46a`
- message: `feat: add explicit OpenAI reference judge`

主要追加:

- `backend/app/ai/reference/openai_reference.py`
- `backend/app/ai/reference/__init__.py`
- `backend/tests/test_openai_reference.py`
- `scripts/run_openai_reference.py`
- `docs/evidence/OPENAI-REFERENCE-PROVIDER-20260903.md`

## 2. 実装上の方針

- OpenAI SDK dependency は追加しない。
- 既存 `OpenAICompatibleAdapter` を再利用する。
- Product Runtime の自動 Routing / Fallback には入れない。
- `OPENAI_API_KEY` の**値は Repository / Provider state / Evidence に保存しない**。
- API key が存在するだけでは外部 API を呼ばない。
- 実通信には既存 `external_call_policy` の Default Deny を通す。
- `FORGE_ALLOW_REAL_PROVIDER_CALLS=1` が無ければ拒否する。
- CLI はさらに `--acknowledge-cloud-data` を要求する。
- OpenAI Reference の判定は Truth ではない。
- Reference 結果単独で `VERIFIED` / `99_PROVEN` / `HARD_GATE_PROVEN` に昇格させない。

## 3. 検証済み

GitHub Actions:

- CI run: `33703950800`
- result: **success**
- jobs: **4 / 4 success**

主要結果:

- `backend/tests`: **2071 passed / 17 skipped**
- `forge_ai/tests`: **747 passed / 10 skipped**
- Flutter analyze: PASS
- Flutter test: PASS
- generated Dart build path: PASS
- reuse-first E2E: PASS
- Flutter web build: PASS
- backend smoke: PASS

OpenAI Reference の Mock Transport（実ネットワークへ出ない模擬通信）で以下を検査済み:

- `/v1/chat/completions` 形式
- Bearer Authorization
- JSON Schema Structured Output
- API key を Provider state に保持しない
- API key 存在だけでは通信できない
- Reference Judge Prompt 内の request / candidate / Target Contract を評価対象データとして扱う境界

## 4. 未実証

以下は **PASS と書かない**。

- 実 OpenAI API の HTTP 200
- 実 Account での指定 Model 利用可否
- 実 OpenAI Reference の Benchmark 品質
- Local / deterministic Forge と OpenAI Reference の統計比較
- 121能力の99%証明
- 能力差0

今回の実 OpenAI API call count: **0**。

## 5. 0円戦略との関係

OpenAI Reference は製品の成立条件ではなく、**0円本線の弱点発見・校正用**。

有料 API を使った結果を、そのまま「0円 Product Runtime の能力」として数えない。

能力差が縮んだと数えるのは、Reference が見つけた差分を Local / deterministic / OSS 側へ反映し、同じ Target Contract を0円経路だけで満たした時。

## 6. 次の作業

### Engineering Priority 1: Sandbox / EXT-08

現在 Self-Extension の生成物は Gate を複数通しているが、test/build をホスト権限で実行しており、**本当の隔離実行環境が無い**。

次にやる本線:

1. 現在の Self-Extension 実行経路を全追跡する。
2. Source生成 → static scan → test/build/runtime probe の各 effect（副作用）を列挙する。
3. file / network / process / environment / CPU / RAM / time の権限境界を定義する。
4. Default Deny の Sandbox Contract を作る。
5. Escape / bypass / symlink / path traversal / subprocess / network / env secret leak を壊し試験する。
6. `Verified Artifact Digest = Installed Artifact Digest` を維持する。
7. Sandbox 未通過 Artifact は Promotion 不可にする。
8. CI で guard-break / mutation test を入れる。
9. Capability Matrix の EXT-08 を Evidence に従ってのみ更新する。

### Engineering Priority 2

Frozen Final Holdout（開発Agentから見えない最終評価セット）の運用方式確定。

### Engineering Priority 3

Outcome Episode（最終成功、Repair回数、Fallback率、p95 latency、RAM等）の収録。

## 7. 再開時の最初の確認

再開したAI/PCは、まず以下を確認する。

```text
git branch --show-current
git log -5 --oneline
git status --short
```

期待 branch:

`claude/forge-master-handoff-k46jns`

OpenAI Reference base commit:

`f0eb5bb9a1fdbdcd27234bfa5638ace90942c46a`

この文書より後の commit があれば、その差分を先に確認してから作業を再開する。
