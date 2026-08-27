# Machine-Independent Policy — 常設の実行PCを仮定しない

> **上位文書**: `docs/PRODUCT-DIRECTION.md` / `docs/LEARNABLE-LOCAL-AI-VISION.md`
> **記録日**: 2026-08-26（FORGE-020A1、CEO指示）

---

## 1. 前提

Forge の検証は、**そのときに使えるPCで行う。**

* **常設の実行PCを仮定しない**
* 開発 container / CEO の手元 / Reviewer の環境 / 将来の別マシン——
  どれも「一時的な Execution Host」である
* **その時 Local Model を実行できるPCが、そのセッションの
  Execution Host になる**

> **「別実機」という固定された1台は存在しない**（020A2 §8 で表現を
> 訂正した）。020A の HANDOFF は「Claude container vs 別実機」と書いて
> いたが、これは常設 Host が在るかのような読み方を生む。
> 在るのは**そのときのセッションの Execution Host**だけである。

「あのマシンで測った」という記憶に依存する運用は成立しない。
記憶は共有されないからである。

## 2. 共有状態は GitHub だけ

| | 置き場 | 共有されるか |
|---|---|---|
| コード / テスト | GitHub | ✅ |
| 申し送り | `docs/HANDOFF.md` | ✅ |
| 実測の証拠 | `docs/evidence/` `docs/visual-evidence/` | ✅ |
| チャット | — | ❌ **存在しないのと同じ**（`CLAUDE.md` §1） |
| 「あのマシンでは動いた」 | — | ❌ |

**GitHub に無い事実は、無い。**

## 3. マシン固有のものを GitHub へ固定しない

置いてはならないもの:

* 絶対パス（`/Users/xxx/...` `C:\Users\...`）
* ホスト名・IP・ポートの決め打ち（設定の**既定値**としてなら可）
* そのマシンにしか無い Runtime / GPU の前提
* **秘密の値**（`CLAUDE.md` §4。持ってよいのは環境変数の**名前**だけ）

置いてよいもの:

* 環境変数の**名前**と、その意味
* 「こういう Runtime が在れば動く」という条件
* **実測したときのホストの性質**（`host_id` / RAM / GPU の有無）——
  これは「どこで測ったか」の記録であり、設定ではない

## 4. 作業開始時に、そのPCの能力を検出する

```
python scripts/forge_doctor.py
```

読むだけである。**何もインストールしない。何も書き換えない。**
秘密は「設定されているか」だけを見る（値も長さも先頭数文字も出さない）。

出力は「このPCで通せる検証」の一覧である。

| 検証 | 必要なもの |
|---|---|
| backend / forge_ai のテスト | Python |
| Renderer のテスト | Flutter |
| Quality Gate v2（実描画・撮影） | Flutter + Chromium + Playwright |
| GitHub 同期 | git + github.com |
| open-weight model の取得 | huggingface.co / ollama.com |
| **Level 0**（実 Local Model の E2E） | Runtime が起動していること |
| **Level 0.5**（Baseline Benchmark） | Runtime + 重みの digest（**GPU は必須ではない**。CPU 計測も実測である） |

## 5. 実行できない項目は UNVERIFIED

**出来ないことを「失敗した」と書かない。**

* `UNVERIFIED` — このPCでは測れなかった
* `FAILED` — 測って、通らなかった
* `INVALID_PROBE` — 測定そのものが成立していなかった
  （例: Level 0 の probe が Curated へ落ちた）

3つを混ぜると、次に読む人が「Local Model は駄目らしい」と誤解する。
`CLAUDE.md` §3「分からないものを楽観側へ倒さない」の裏返しで、
**分からないものを悲観側へも倒さない。**

## 6. 現在の状態（2026-08-26、開発 container 実測）

`scripts/forge_doctor.py` の出力より:

```
✓ backend / forge_ai のテスト
✓ Renderer のテスト
✓ Quality Gate v2（実描画・撮影）
✓ GitHub 同期
✗ open-weight model の取得      （huggingface.co / ollama.com が到達不能）
✗ Level 0（実 Local Model の E2E）（Runtime が無い）
✗ Level 0.5（Baseline Benchmark） （Runtime が無い。GPU の有無は条件ではない）
```

## 6.1 GPU は Benchmark の前提条件ではない（020A2 §8 で訂正）

020A1 の `forge_doctor.py` は `level0_5_baseline` の条件に GPU を
入れていた。**これは誤りである。**

CPU で Real Model が動き、実測できるなら **Benchmark 自体は有効**で
ある。遅くても、出た数字は実測である。

GPU / VRAM は別の意味を持つ:

| | 何の Evidence か |
|---|---|
| Runtime + 重みの digest | **Benchmark が成立するか** |
| GPU / VRAM | **性能・遅延・現実的に載るモデルの大きさ** |

「GPU 無し = Benchmark 不能」と固定すると、CPU で回せる小型モデルの
実測が永久に取れない。`forge_doctor.py` は両方を別々に報告する。

したがって **Real Local Model runs = 0 のまま**であり、
`LEARNABLE-LOCAL-AI-VISION.md` の Level 0 は **UNVERIFIED** を維持する。

2026-08-27に当該PCへOllama/Qwen 7Bが用意され、実測可能になった。
ただし公式実測はFAILED 1回、INVALID_PROBE 2回で、PASSはまだ無い。
したがってReal Local Model runsは0のままである。

## 7. Execution Host になったPCでやること

```
# 1. 何が出来るPCかを確かめる
python scripts/forge_doctor.py

# 2. Level 0 が「可」なら測る
export FORGE_LOCAL_BASE_URL=http://127.0.0.1:11434/v1
export FORGE_LOCAL_MODEL=<pull したモデル>
python scripts/verify_local_model_level0.py

# 3. 出た JSON を commit して push する
git add docs/evidence/level0 && git commit && git push
```

**PASS したときだけ** `Real Local Model runs` を増やす。
**勝手に増やさない**（CEO指示）。
