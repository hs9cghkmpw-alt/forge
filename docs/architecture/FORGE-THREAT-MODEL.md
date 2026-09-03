# Forge Threat Model — 「Security 100%」の意味を確定させる

**Status:** ACTIVE（2026-09-03 新設）

**Scope:** Forge 本体、生成される Tool、Self-Extension 経路、Evidence

---

## 0. 「100%」は何の 100% か

> **禁止:** 「Security 100%」を「世界中の未知脆弱性が存在しない」という意味で
> 使うこと。それは誰にも証明できない。証明できないものを主張すると、
> Evidence 全体の信用が落ちる。

正しい表現はこれである。

> **定義された Threat Model、定義された Corpus、定義された Hard Gate の内側で、
> Critical Violation が 0 件。**

3 つを毎回明示する。

1. **どの脅威を見たか**（Threat Model）
2. **何に対して見たか**（Corpus）
3. **何を違反とするか**（Hard Gate）

**未検査領域を安全と主張しない。** 下表の `未検査` は、安全という意味では
なく、見ていないという意味である。

---

## 1. Threat Model

| ID | 脅威 | 何が起きるか | 現状 | 対応 |
|---|---|---|---|---|
| T1 | **Sandbox escape** | 生成 Dart の test/build がホスト権限で動き、File / Process / Network / Secret へ届く | **未対応**（Sandbox 未実装、ADR-015 §4.2） | W1: 隔離実行 |
| T2 | **Prompt Injection** | 利用者入力や取り込んだ文書が、Forge への指示として解釈される | 部分対応（`injection_scan.py`） | Corpus と Hard Gate が未定義 |
| T3 | **Tool Injection** | Agent の Tool 呼び出しが、意図しない副作用へ誘導される | 部分対応（Tool Broker / Permission Broker） | Corpus 未定義 |
| T4 | **RAG poisoning** | 取り込んだ知識が汚染され、生成物へ伝播する | **未検査** | 出所の固定と署名 |
| T5 | **Dataset poisoning** | 学習・Promotion に使う Episode が汚染される | **未検査** | Episode の provenance |
| T6 | **Model swap** | 期待した Model と違う Model が応答する（digest 不一致） | 部分対応（`actually_used_model` を記録） | Model digest の固定 |
| T7 | **Supply chain** | 生成物や依存が、許可していない package を引き込む | **未対応**（依存 allowlist 無し） | W4: 依存 allowlist |
| T8 | **Secret 漏洩** | API キー等が Source / Log / Evidence / Report へ出る | 対応（CLAUDE.md §4、`redact_provider_identity_for_logs`） | 継続 |
| T9 | **無承認の外部通信** | キーが存在するだけで外部 Provider が呼ばれる | **対応済み**（`external_call_policy.py`、Default Deny） | 完了 |
| T10 | **Evidence 改竄・自己申告** | 呼んでいない Provider、動かしていない試験を Evidence が名乗る | **対応済み**（`model_call_ledger.py`、`check_capability_matrix.py`） | 継続 |
| T11 | **Permission bypass** | Tier C（Network / Credential / OS / 決済 / 高 Risk）が無承認で自動実行される | **未対応**（Tier がコードで強制されていない） | W3 |
| T12 | **生成 Tool の権限逸脱** | 生成された Tool が、宣言していない権限を使う | **未対応**（Permission Manifest 無し） | W2 |

### 1.1 T9 の詳細（2026-09-02 の事故）

作業ホストの `.env` に実 API キーがあり、backend を起動しただけで実 Gemini API
が呼ばれた。**キーの存在を同意として扱っていた**ことが原因である。

対応: `backend/app/ai/gateway/external_call_policy.py`。Default Deny。
Cloud への通信は `FORGE_ALLOW_REAL_PROVIDER_CALLS=1` の明示が必要。テスト中は
さらに `FORGE_REAL_PROVIDER_TEST=1` が必要。値が `1/true/yes/on` 以外なら
**fail closed**。

Hard Gate: `backend/tests/test_external_call_policy.py`。
egress point の Policy 確認を外すと落ちる（配線破壊試験で確認済み）。

---

## 2. Hard Gate（違反 0 件が要求されるもの）

| Gate | 判定 | 現状 |
|---|---|---|
| HG-1 | Sandbox 外への Network / File / Process / Secret access = 0 件 | **未検査**（Sandbox 無し） |
| HG-2 | 無承認の外部 Provider 通信 = 0 件 | 実装済み・テスト済み |
| HG-3 | Secret の Source / Log / Evidence / Report への出現 = 0 件 | 実装済み |
| HG-4 | 未検証 Artifact の Promotion = 0 件 | 部分（digest / build / loaded / PROMOTED は実装済み、Sandbox / Permission が Gate 列に無い） |
| HG-5 | Tier C の無承認自動実行 = 0 件 | **未対応** |
| HG-6 | 呼んでいない Provider の Evidence 記録 = 0 件 | 実装済み・テスト済み |
| HG-7 | Prompt Injection による Forge 指示の乗っ取り = 0 件 | **Corpus 未定義** |

---

## 3. Corpus（何に対して測るか）

現時点で**定義済みの Corpus は存在しない**。したがって

> Security について `HARD_GATE_PROVEN` を名乗れる項目は 0 件である。

必要な Corpus:

| Corpus | 対象 Gate | 規模の目安 |
|---|---|---|
| C1 escape 試行 | HG-1 | Network / File / Process / Secret の各系統 |
| C2 Injection 文 | HG-7 | 直接指示 / 文書埋め込み / 多段 |
| C3 Tool 誘導 | T3 | Tool ごとの誤用パターン |
| C4 汚染知識 | T4 / T5 | 出所偽装、内容矛盾 |
| C5 依存改竄 | T7 | 未許可 package、version 差し替え |

---

## 4. 報告の書き方（テンプレート）

```text
Security 結果（2026-XX-XX）
  Threat Model: FORGE-THREAT-MODEL.md v1（T1〜T12）
  Corpus:       C1(n=..), C2(n=..)
  Hard Gate:    HG-2, HG-3, HG-6 について Critical Violation 0 件
  未検査:       T1, T4, T5, T7, T11, T12（安全という意味ではない）
```

**「Security 100%」とだけ書いた報告は受理しない。**
