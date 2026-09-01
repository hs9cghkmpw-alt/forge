# Forge Self-Contained Distribution Policy

**Status:** Product / Architecture Direction  
**Date:** 2026-09-01  
**Scope:** Desktop distribution, Local AI runtime, model delivery, first-run setup, updates

---

## 0. 結論

Forge の完成版では、利用者に次の作業を要求しない。

- Ollama 等の Local AI Runtime を手動インストールする
- PowerShell / Terminal を開く
- `ollama pull` を実行する
- Python や仮想環境を準備する
- Backend を手動起動する
- `FORGE_LOCAL_BASE_URL` / `FORGE_LOCAL_MODEL` 等の環境変数を手動設定する
- Frontend と Backend を別々に起動する

利用者から見た Forge は **1つのアプリ**でなければならない。

```text
Forge Installer
      ↓
インストール
      ↓
Forge を起動
      ↓
そのまま使える
```

内部で複数のプロセス・Runtime・Model・Backend が動いていても、通常利用者へその複雑さを露出しない。

---

## 1. 基本方針

Forge の配布単位は、単なる Flutter UI ではない。

```text
Forge Product
  ├─ Desktop UI
  ├─ Forge Backend
  ├─ Forge Intelligence / Capability System
  ├─ Local AI Runtime
  ├─ Local Model
  ├─ Runtime / Model Manager
  ├─ Health Check
  ├─ Update Manager
  └─ Recovery / Diagnostics
```

これらを利用者には **Forge という1製品**として提供する。

開発時に使用している Ollama・Python・uvicorn・環境変数・PowerShell は、実装手段であって製品 UX ではない。

---

## 2. 標準配布方式

通常版の第一候補は **本体を先に配布し、初回起動時に適切な Local Model を自動取得する方式**とする。

```text
Forge Setup
   ↓
本体 / Backend / Local Runtime を配置
   ↓
初回起動
   ↓
PC 性能を検査
   ↓
適切なモデルを決定
   ↓
必要な場合のみモデルを自動 Download
   ↓
Integrity Check
   ↓
Local Runtime 起動
   ↓
Backend 起動
   ↓
Health Check
   ↓
Forge UI 起動
```

利用者にモデル名、Runtime 名、URL、Port、環境変数を選ばせることを標準動作にしない。

---

## 3. 完全オフライン配布も正式に許容する

ネットワーク接続できない環境向けに、Local Model まで同梱した **Offline Bundle** を作れる構造にする。

```text
Forge Offline Bundle
  ├─ Forge
  ├─ Backend
  ├─ Local AI Runtime
  └─ Approved Local Model
```

Offline Bundle は容量が大きくなることを許容する。

一方、通常版はインストーラー容量を抑えるため、初回セットアップでモデルを取得してよい。

したがって配布方式は最低でも次の2種類を想定する。

1. **Standard** — Runtime 同梱、Model は初回自動取得
2. **Offline** — Runtime + Model をすべて同梱

Cloud-only や Enterprise 専用構成が必要になった場合も、同じ Runtime Manager の上で扱えるようにする。

---

## 4. Ollama は製品要件ではない

現行開発環境では Ollama を Local Model Runtime として使用しているが、**Forge = Ollama ではない**。

Forge が依存する契約は Local Model Runtime そのものではなく、Forge が定義する Adapter / Provider 契約である。

したがって将来は以下を交換可能にする。

- Ollama
- llama.cpp / llama-server
- LM Studio compatible runtime
- vLLM
- その他の検証済み OpenAI-compatible Local Runtime
- Forge 専用の埋め込み Runtime

完成版では、必要であれば Runtime 自体を Forge の内部コンポーネントとして同梱し、利用者に Ollama を別製品として意識させない。

---

## 5. PC 性能を見て Local Model を選ぶ

1つの Model をすべての PC に固定しない。

起動前または初回セットアップ時に、少なくとも次を確認する。

- OS / Architecture
- CPU
- RAM
- GPU の有無
- VRAM
- 空き Disk
- Local Runtime の利用可否

その結果から、Forge が検証済み Model Profile を選ぶ。

例:

```text
Low resource PC
    → 小型モデル

Mid-range PC
    → 中型モデル

GPU / high-memory PC
    → 高性能モデル
```

ただし、**モデルの大きさだけで採用しない**。

採用判断は Forge Benchmark による、少なくとも以下の実測を使う。

- latency
- schema compliance
- semantic accuracy
- task success rate
- memory usage
- startup / warm-up time
- error rate

「高性能 PC だから最大モデルを入れる」のではなく、Forge Task に対して Evidence 上もっとも適切な構成を選ぶ。

---

## 6. 初回起動と Warm-up

Local Model は Cold Start（初回読み込み）が遅くなる場合がある。

そのため Forge は、必要に応じて起動時に Model を事前ロードし、利用者が最初の要求を入力してから Model Load を始める構造を避ける。

ただし Warm-up のために起動を過度に遅らせない。

可能なら次のように分離する。

```text
Forge UI 起動
      ↓
利用者はすぐ操作可能
      ↓ parallel
Local Runtime / Model warm-up
```

既存 Capability だけで処理できる要求は Local LLM の起動完了を待たず実行可能であることが望ましい。

これは Reuse-first 方針と一致する。

> 持っている能力は組み合わせる。  
> 足りない能力は作る。  
> 作った能力は検証し、再利用可能な Forge Capability として取り込む。

---

## 7. 「全部 AI に投げる」構造を配布上の前提にしない

Local AI を同梱できることと、すべての操作を Local LLM に処理させることは別問題である。

完成版でも Reuse-first を基本とする。

```text
User Need
   ↓
Existing Capability で解決可能？
   ├─ YES → 即再利用 / 組み合わせ
   └─ NO
        ↓
     AI / Planning
        ↓
     Missing Capability のみ生成
        ↓
     Build / Test / Verify
        ↓
     Install / Reuse
```

Local Model は Forge の知能の一部であって、Forge 全体そのものではない。

---

## 8. Backend / Runtime は自動管理する

製品版では Backend や Local Runtime の手動起動を要求しない。

Forge Launcher / Runtime Manager が次を担当する。

- 必要プロセスの起動
- Port の決定
- Health Check
- 起動順序制御
- Crash 検知
- 必要な再起動
- 多重起動防止
- 終了時の後始末
- Version compatibility 確認

固定 Port を無条件に前提とせず、競合時にも回復可能な設計を優先する。

Frontend は Runtime Manager が確定した Backend endpoint を安全に受け取る。

---

## 9. Python 開発環境を利用者へ要求しない

利用者が `pip install`、`.venv` 作成、依存 package 導入を行う構成は禁止する。

Backend は製品ビルド時に自己完結した実行物として package する。

実現方式は実装段階で Benchmark /保守性 /配布サイズを比較して決めるが、利用者 UX は次を満たすこと。

```text
Python installed?  → 知らなくてよい
pip installed?     → 知らなくてよい
venv?              → 知らなくてよい
uvicorn?           → 知らなくてよい
```

---

## 10. Model Download は安全に行う

自動 Download を行う場合、最低限次を実装する。

- HTTPS
- Download 元の allowlist
- Model / Runtime version 固定または検証可能な manifest
- SHA-256 等による integrity verification
- 中断再開
- 不完全 Download の検知
- Disk 容量の事前確認
- Install 完了前の atomic promotion
- 壊れた Model の rollback / 再取得

Download しただけの Model を即「利用可能」にしない。

```text
Download
  → Verify
  → Minimal Runtime Test
  → Promote
  → Use
```

とする。

---

## 11. Model / Runtime のライセンスを配布条件に含める

技術的に Bundle 可能であることと、再配布可能であることは別である。

採用する Runtime / Model ごとに、リリース前に必ず以下を確認する。

- 再配布条件
- 商用利用条件
- attribution
- license text 同梱要否
- model-specific restrictions

確認が完了していない Model を正式 Installer へ含めない。

---

## 12. 更新は分離する

Forge 本体、Runtime、Model、Capability は別々に version 管理できるようにする。

```text
Forge App Update
Local Runtime Update
Model Update
Capability Update
```

を独立させる。

Model を更新するたびに巨大な Forge 本体を再 Download させない。

逆に UI の小変更だけで Model を再取得させない。

更新後は compatibility / health / benchmark smoke test を実行し、不成立なら直前の正常構成へ戻せることを目標とする。

---

## 13. 利用者へ見せる状態

内部エラーをそのまま見せない。

例:

```text
AI を準備しています…
モデルをダウンロードしています… 42%
初回セットアップを完了しています…
Forge を起動しています…
```

問題が起きた場合は、利用者が直せる内容だけを伝える。

詳細な Provider / Runtime / Port / stack trace は Diagnostics へ分離する。

開発者向け Diagnostics では Evidence を残すが、Secret や個人情報を出さない。

---

## 14. 配布成功の最低条件

「Installer が作れた」だけでは完成ではない。

クリーンな Windows 環境などで、少なくとも次を自動または実機 E2E で確認する。

```text
Install
→ First Launch
→ Runtime Setup
→ Model Setup
→ Backend Health PASS
→ Local AI Task PASS
→ Forge UI PASS
→ Natural Language Request
→ Generated / Reused Tool Render PASS
→ Close
→ Reopen
→ No Re-setup Required
```

さらに失敗系として少なくとも以下を確認する。

- Network unavailable
- Download interrupted
- Disk insufficient
- Port collision
- Runtime crash
- Model corrupted
- Model incompatible
- Old installation remains
- Upgrade failure
- Uninstall / reinstall

利用者が PowerShell を開かなければ復旧できない状態を正式完成扱いしない。

---

## 15. 現在の実機試験との関係

2026-09-01 の開発実機では、手動で以下を確認した。

- Ollama installed / running
- Local Model direct invocation
- Forge Backend startup
- Forge Backend → Local Model
- `simulated=false` の Local Model response

これは **配布完成の証明ではない**。

現在の手動手順は、完成版で自動化・内包すべき作業を発見するための開発 Evidence として扱う。

現在のモデルサイズ・速度は採用確定値ではなく、今後の Benchmark の入力データである。

---

## 16. Product Requirement

最終的な利用者体験を次で固定する。

> **Forge をインストールすれば Forge が使える。**
>
> Local AI、Runtime、Backend、Model、設定、起動順序、Health Check は Forge 側の責任で管理する。
>
> 利用者に開発環境構築を要求しない。

技術構成は将来変更してよい。

しかし、この UX 要件を満たすために内部実装を選ぶのであって、内部実装の都合で利用者へ手作業を押し付けない。

---

## 17. 次の実装段階

この文書は現時点では **方針固定**であり、Installer 実装完了を意味しない。

次の設計・実装では少なくとも以下を詰める。

1. Windows Packaging 方式
2. Backend executable 化方式
3. Bundled Local Runtime の候補比較
4. Model manifest / downloader
5. Hardware profiler
6. Model selector
7. Runtime manager / process supervisor
8. Health / recovery flow
9. Offline Bundle
10. Update / rollback
11. License compliance
12. Clean-machine E2E

この実装を進める際も、Forge の最上位原則である **Reuse-first / Evidence-first / Local-first** を崩さない。
