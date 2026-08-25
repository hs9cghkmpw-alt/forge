# Forge Handoff

- Branch: `claude/forge-master-handoff-k46jns`
- Start HEAD: `63ad43403606c9731f76c98248a9b0e9149e94bf`
- Implementation Agent: **Claude Code**
- Current phase: R1 Generated App Quality / Growing AI
- Current task: **FORGE-019C/020 — Revision Atomic Closure + Local
  Generative Intelligence Foundation**
- **Real Local Model runs: 0**（環境要因。下記「CEOへの依頼」）

---

## CEOへの依頼（先に読んでほしいところ）

### 1. 実 Local Model を動かすには、**環境の network policy** が要る

install の許可だけでは足りない。実測:

```
https://pypi.org/simple/  → 200
https://huggingface.co/   → 403（proxy が拒否）
https://ollama.com/       → 403
https://github.com/       → 403
```

**モデル重みの取得先が塞がっている。** この container に Ollama も
llama.cpp も torch も無く、GPU も無い（RAM は 15 GB あるので容量は足りる）。

必要なもの:

| | |
|---|---|
| Runtime | Ollama もしくは llama.cpp（`llama-server`）。**どちらも OpenAI互換なので既存の `LocalModelProvider` が `base_url` だけで繋がる** |
| Model | `qwen2.5:1.5b-instruct`（約 1.0 GB / Q4）または `qwen2.5:7b-instruct`（約 4.5 GB / Q4） |
| RAM 目安 | 1.5B で 4 GB、7B で 8〜10 GB。**この環境で足りる** |
| 追加で必要 | **`huggingface.co` / `ollama.com` への到達許可**（network policy） |

判断が要るのは「install してよいか」ではなく「**この環境から model を
取れるようにするか / 別の環境で走らせるか**」である。

### 2. 前セッションから残っている件

以前のセッションで貼られた OpenAI API key（`sk-proj-...`）は
**どこにも保存していない**が、**まだ失効させていないなら失効させてほしい。**

---

## 何をしたか

### 019C — Revision を本当に閉じた

独立レビューの4点は**すべて現在のコードで再現できた**。先に再現テストを
書いて FAIL させてから直した。

| 指摘 | 直した形 |
|---|---|
| A. advance 失敗で CORRECTED だけ残る | **順序を変えた。** CAS で版を進めてから追記する。落ちうる段が追記より前に来たので、巻き戻す必要そのものが消えた |
| B. 投影失敗で確定済み Revision が API 失敗 | **投影を分離。** `LearningProjectionOutbox` へ pending として残る。API は成功のまま |
| C. 「単一プロセスだから割り込まない」は成り立たない | **前提を捨てた。** per-artifact lock + compare-and-swap + replay 予約 |
| D. enum の宣言と本番到達可能な操作が不一致 | **3段に分けた。** production_supported は **1件だけ** |

Rejected な Revision は **RevisionRecord 0 / FeedbackEvent 0 /
LearningEvent 0 / 版 0 / replay 0**。

### 020 — 実 Local Model が要らない部分を作った

- **Agent**: Tool Broker / Permission Broker（4段）/ Sandbox /
  Repair Loop（予算付き）。**Model へ任意 shell 文字列を渡す口は無い**
- **Web**: search / fetch / browser。本文は `UntrustedContent` に包まれ、
  **解かないと取り出せない**（Web を命令として扱わない）
- **Learning**: GenerationEpisode / Teacher 比較 / Training Gym /
  Novel Benchmark / Dataset Builder / Knowledge 昇格 Gate /
  Adapter / Self-Extension

### 方向の文書を新設した

`docs/GENERATIVE-SOFTWARE-DIRECTION.md`
——「有限Widget Builderにしない」を、実装の都合で崩さないための下限。
`PRODUCT-DIRECTION.md` は**変更していない**。

---

## Production wiring

```
Flutter Host / 会話
  → artifact capability（handle）
  → version token / document binding
  → replay 予約（同じ論理要求を2本走らせない）      019C §8
  → per-artifact lock（同じ生成物を直列化）          019C §7
    → TargetResolver / 全体再生成fallback
    → Validator + Semantic Design Critic
    → 本番で使ってよい操作かの検査                    019C §9
    → [ prepare → stage → commit(CAS→追記) ]         019C §4
  ← lock 解放
  → project → Learning Outbox                        019C §6
  → GenerationEpisode                                020 §18 ★今回配線
  → 新しい artifact version → Flutter render
```

| | 状態 |
|---|---|
| Revision 系 | ✅ **本番配線済み** |
| Benchmark → LocalPromotionGate → routing | ✅ 配線済み・**昇格0件**（実測が無い） |
| Agent / Web / Teacher / Gym / Novel / Dataset / Adapter | ⬜ **契約のみ。本番配線なし** |

未配線であることも**テストで固定した**——配線したのに文書を直さないと
`test_forge_020_production_wiring.py` が落ちる。

---

## Tests / Evidence

**LOCAL と CI を混ぜない。**

| | LOCAL（今回の実測） |
|---|---|
| backend | **1,706 passed / 16 skipped** |
| forge_ai | **521 passed** |
| Flutter test | **514 passed** |
| `flutter analyze --fatal-infos --fatal-warnings` | **No issues found** |
| `flutter build web --debug` | 成功 |
| backend smoke（起動 / health / CORS / generate） | 成功 |
| ruff（変更ファイル） | All checks passed |

**CI の実測**（run `32910317758` / `b89d090`、**4 job すべて success**）:

| | CI |
|---|---|
| backend Python 3.11 | **1,705 passed / 17 skipped** |
| backend Python 3.12 | **1,705 passed / 17 skipped** |
| forge_ai | **521 passed** |
| Flutter | **514 tests passed** / analyze 通過 / build web ✓ |

> LOCAL は `1,706 / 16`。`FORGE_DEFAULT_PROVIDER=mock` の有無で skip が
> 1件変わる（019B でも同じずれを記録済み）。**混ぜない。**
>
> Flutter SDK は **LOCAL 3.44.9 / CI 3.47.1**。Visual Evidence は
> 3.44.9 で撮っている。

| guard の種類 | 数 |
|---|---|
| behavior guards | **178** |
| static protocol checks | **8** |
| **real source mutation rounds** | **22** |

22 round すべて KILLED。**うち3 round は最初 SURVIVED だった。**

- M10 は**本物の置物**だった（表と実装のずれを1本も検査していなかった）
- M6 は**冗長な守り**を壊していた（判断を1箇所へまとめてから再実行）
- M1 は対象テストの指定が狭かった

---

## Visual — **実施した**（019A/019B の `UNVERIFIED` を解消）

`docs/visual-evidence/FORGE-019C/manifest.md`

本番の `RevisionService` が出した文書を **Flutter で実描画し、Chromium で
撮り、画像を開いて目で確認した。**

結果: overlap / overflow / clipping / alignment / spacing 問題なし。
「残高をもっと目立たせて」の後、**残高が最大・濃色になり、収入は
`finance.income` へ降りた**——意図どおり。

### 019A/019B の `UNVERIFIED` の理由は誤りだった

「この環境に Flutter SDK が無い」と書いてあったが、**`/opt/flutter` に
Flutter 3.44.9 stable が入っている。** 確認せずに書いていた。

### 途中で真っ白なPNGを1回作った

engine 未起動のまま撮っており4枚とも真っ白だったが、**コマンドは成功して
見えた**。画像を開かなければ「実描画の証拠」として提出していた。
`AGENTS.md` の「PNGを生成しただけを Visual Review と呼ばない」は
この形の失敗を指している。

再現用に `scripts/capture_visual_evidence.py` を追加した（PowerShell 版と
違い、この環境で動く）。

---

## 見つけた製品側の問題（未修正）

**Web build に同梱フォントが無い**（`TECH_DEBT.md` TD75(b)）。

`pubspec.yaml` に `fonts:` が無く、`fontFamily: 'Helvetica'` である。
Flutter Web(CanvasKit) は system font を使わないので、
`fonts.gstatic.com` へ届かない環境では**文字が1文字も表示されない**。
「遅い」ではなく「何も出ない」という壊れ方をする。

撮影時はフォントを差し替えて回避したが、**製品側は直っていない。**

---

## UNVERIFIED

- **実 Local Model**（runs 0。環境要因、上記）
- **実 Web への往復**（Search Provider 未設定・proxy 拒否。単体テストのみ）
- **実 Cloud Provider への往復**（実APIを呼んでいない）
- **プロセス再起動を跨ぐ replay / outbox**（in-memory。安全側に壊れる）
- **複数プロセスでの直列化**（プロセス内 lock のため）
- Visual の**字形**は本番と違う（撮影時にフォントを差し替えたため）。
  配置・重なり・はみ出し・階層は確認済み

---

## Technical Debt（増減）

**解消**: advance 失敗時の atomicity / `admit`と`record`の間の前提 /
`publish()` の差し替え点（半分）。

**新規**: TD80 Outbox が NOT DURABLE / TD81 replay 予約がプロセス内 /
TD82 lock がプロセス内 / TD83 意味的操作の実装が1件 / TD84 020 の各層が
本番未配線 / TD75(b) Web build に同梱フォントが無い。

---

## Next task

**FORGE-020A — Real Local Model Runtime。**

上の「CEOへの依頼」が解決してから着手する。解決すれば

```
LocalModelProvider（既存・OpenAI互換）
  → Provider Registry（既存）
  → AIRouter（既存）
  → BenchmarkRun
  → LocalPromotionGate（既存・配線済み）
  → routing evidence
```

まで**Provider を1つ足すだけ**で通る。並行 architecture は作らない。

その後: 020B Tool-Using Local Agent の本番配線 → 020C Episode 拡張 →
020E Novel Benchmark の初回 run。

## Next three moves

1. push した HEAD / diff / tests / CI / mutation を独立レビューで確認する
2. 実 Local Model の環境（network policy / 別マシン）を決める
3. TD75(b)（同梱フォント）を直すかどうかを決める
