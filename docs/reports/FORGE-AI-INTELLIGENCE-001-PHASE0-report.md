# FORGE-AI-INTELLIGENCE-001 PHASE 0 — Baseline再確認 実施レポート

**Ref:** FORGE-AI-INTELLIGENCE-001 PHASE 0
**担当:** Principal Engineer(Claude)　**日付:** 2026-08-10

---

## 0. 背景

CEOから「FORGE — MASTER HANDOFF」文書とともに、`forge`ワークスペースの
GitHubリポジトリ(`hs9cghkmpw-alt/forge`)での作業を依頼された。着手前に
リポジトリの実状態を確認したところ、**GitHubリポジトリは空(コミット0件、
ブランチ0件)**だった。

CEOから添付されたzip3点(`forgev0.6forgeirv1`・
`forgev2phase1workspacefoundation`・`forgev2phase2step1folder`)を
実際に展開・diffした結果、3点は`irv1`→`phase1workspace`→`phase2step1`の
順で厳密な線形進行(それぞれ368/419/432ファイル、後者は前者の
strict superset)であることを確認し、最新の`phase2step1`を実リポジトリの
baselineとして復元・commit・push した(このコミット自体が本Taskの
成果物の一部)。

---

## 1. 発見した重大な齟齬(報告 vs 実ファイル)

MASTER HANDOFF文書は「Phase1〜3 Native Intelligence」(Output Safety /
Prompt Injection Guard / IR Versioning、TD20〜TD22解消済み)が既に実装・
マージ済みであると記述し、baseline testの数値として
`forge_ai: 416 passed` / `backend: 667 passed, skipped=63` を挙げていた。

実際に`pytest`を実行して確認した数値は以下の通り、大きく異なる。

| 項目 | 文書の主張 | 実測(2026-08-10) |
|---|---|---|
| `forge_ai` tests | 416 passed | **390 passed** |
| `backend` tests | 667 passed, 63 skipped | **518 passed, 12 skipped** |
| 合算 | — | **908 passed, 12 skipped**(重複実行時) |
| `output_safety.py` | 存在 | リポジトリ全体を`grep`しても**該当なし** |
| `injection_guard.py` | 存在 | **該当なし** |
| `schema_version`(IR Versioning) | 存在 | **該当なし** |
| CHANGELOG最新行 | Native Intelligence Phase1-3 | **Task043(2026-07-22、Confidence Model Review、設計レビューのみ・コード変更なし)** |

CEOに確認したところ(本レポート作成前に`AskUserQuestion`で確認済み)、
「Phase1-3 Native Intelligenceのコードは別に存在する可能性があるが、
今回は追わず、PHASE0(baseline確認)とIntegration Adapterのみ実施する」
という指示を受けた。TD20(Output Safety)・TD21(Injection Guard)・
TD22(IR Versioning)は、**今回のセッションでは意図的に着手していない**
(CEO指示による範囲外)。この3件を別途どこかで実装する場合、既存コードとの
重複実装を避けるため、着手前に必ずCEOに現物の所在を確認すること。

---

## 2. Integration Adapter(TD16)は既に実装・接続済みだった

FORGE-AI-INTELLIGENCE-001 PHASE 1として「forge_ai公開API ↔ backend
integration ↔ backend Runtime」の境界確立(Integration Adapter)を
新規実装する予定だったが、実ファイル監査の結果、**この作業は既に
完了していた**ことが判明した。

- `docs/spec/ADAPTER_CONTRACT_V1.md`(v1.1、「CEO実コード監査済み」と
  明記されたADR)。
- `backend/app/ai/runtime/forge_ai_adapter.py`(forge_ai型→backend型の
  Facade変換、262行)。
- `backend/app/ai/runtime/forge_ai_provider_bridge.py`(`forge_ai.
  AIProvider` Protocol実装、106行)。
- `backend/app/ai/runtime/prompt_pipeline.py`が`forge_ai.core.pipeline.
  run_cognitive_pipeline()`を実際に1回呼び出しており、
  `backend/app/routers/ai.py`のHTTPエンドポイントまで実際に配線済み。
- `backend/tests/test_forge_ai_adapter.py`ほか、関連テスト18件が実際に
  `pytest`でPASSすることを確認済み。

`TECH_DEBT.md`のTD16(「Native AI(forge_ai/)とbackend/app/ai/runtime/が
未接続」)は、この実装より前に書かれたまま更新されていなかった
**stale(古い)ドキュメント**であることが分かった。新規コードを書く代わりに、
`TECH_DEBT.md`のTD16を実際のコード状態に合わせて訂正した(実装は変更して
いない。ドキュメントの事実誤りのみ修正)。

**設計判断の確認**: ADR(ADAPTER_CONTRACT_V1.md 2章・8.2節)によれば、
`forge_ai`の型(`Intent`/`ApplicationPlan`)と`backend`の型
(`IntentIR`/`PlanIR`)を**統合しない**ことは意図的な設計決定であり
(「粗粒度Facade」方式、型統合案は却下案として明記済み)、TD16の
「型統合が必要」という当初の懸念は、Facade方式を採用したことで
別の形で解消されている。これはギャップではなく承認済みのADR。

---

## 3. 実行した変更(実際の成果物)

1. `hs9cghkmpw-alt/forge`(空リポジトリ)へ、CEO提供の最新snapshot
   (`phase2step1`)を復元・commit・push(`claude/forge-master-handoff-k46jns`
   ブランチ)。
2. `TECH_DEBT.md`のTD16を、実ファイル監査に基づき「解消済み」へ訂正
   (根拠・ファイルパス・テスト件数を明記)。コードの変更は無し。
3. 本レポートの作成。

**新規コード追加は無し**(Integration Adapterは既存、Output Safety等は
CEO指示によりスコープ外)。

---

## 4. 実際に実行したテスト・結果

```
$ python -m pytest backend forge_ai -q
908 passed, 12 skipped in 1.92s
```

```
$ ruff check backend forge_ai
Found 16 errors (11 fixable). 全て本Taskの変更と無関係の既存warning
(未使用import・E402)。今回は変更していない(スコープ外)。
```

Flutter側は本Taskで一切変更していないため未実行(MASTER HANDOFF文書
7章の方針どおり、Claude環境での`flutter analyze`/`flutter test`の
断定は行わない)。

---

## 5. 未実行のもの

- `forge_ai/`・`backend/app/ai/`以外(frontend、database migrations等)の
  実行検証。
- Flutter Runtime全体の`flutter analyze`/`flutter test`(Flutter SDK未導入)。
- TD20(Output Safety)・TD21(Injection Guard)・TD22(IR Versioning)の
  実装(CEO指示により今回スコープ外)。
- FORGE-AI-INTELLIGENCE-001 PHASE 2以降(Reasoning/Planner V2/Template
  Ledger/Benchmark 100/E2E/Architecture Review)。

---

## 6. 推測(事実として扱っていないもの)

- TD20〜TD22の実コードが「別のセッション・別のzipに存在する」という
  可能性は、CEOの発言(選択肢の文言)を根拠にした推測であり、実物を
  確認できていない。次回、実物の所在を確認する必要がある。

---

## 7. Technical Debt

`TECH_DEBT.md`参照。今回新規に追加した項目は無し(TD16の記述を訂正
したのみ)。ADAPTER_CONTRACT_V1.md 8.3節に記載され、今回も未着手のままの
将来拡張点(Streaming応答・Cost/Token計測・Multi-provider fallback・
Caching・`CriticResult.issues`の実質化・`navigation_edges`計算)を
本レポート2章に再掲した。

---

## 8. CEO確認事項

1. TD20(Output Safety)・TD21(Injection Guard)・TD22(IR Versioning)の
   実コードは、本当に別のセッション・別のexportに存在するか。存在する
   場合、そのzip/branchを次回共有してほしい。存在しない場合(MASTER
   HANDOFF文書側の記述が誤りだった場合)、次回そのままゼロから実装して
   良いか、CEO+ChatGPT側で改めて確認したい。
2. `backend`のtest skip数(12件)の内訳確認は今回実施していない
   (範囲外)。次フェーズで必要なら確認する。
3. FORGE-AI-INTELLIGENCE-001 PHASE 2(Reasoning)以降は、上記1の回答を
   踏まえて着手順序を確定したい。

---

## 9. 次提案

- CEO確認事項1の回答を受け取り次第、PHASE 2(ReasoningState)以降へ
  進む。
- TD20〜22が実際に未着手であることが確定した場合、PHASE 4(Safety/
  Injection Pipeline Integration)より前に、これらを新規の
  FORGE-AI-INTELLIGENCE-001内サブフェーズとして先に実装する
  (依存関係上、PHASE 4はTD20〜22の存在を前提にしているため)。
