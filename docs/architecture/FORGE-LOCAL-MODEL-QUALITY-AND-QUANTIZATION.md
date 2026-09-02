# Forge Local Model Quality & Quantization Policy

**Status:** Product / Architecture Direction  
**Date:** 2026-09-01  
**Scope:** Local AI model selection, quantization, distribution size, runtime performance, quality gates

---

## 0. 結論

Forge は、配布容量・RAM 使用量・推論速度を改善するために **量子化（モデル内部の数値表現を低ビット化して軽量化する手法）を正式な検証対象**とする。

ただし、**容量削減を理由に Forge の知能・意味理解・生成品質を下げることを認めない。**

モデルサイズを小さくすること自体を目的にせず、Forge の品質基準を先に定め、その基準を満たす構成の中から、容量・速度・メモリ効率が最も良いものを採用する。

> **Quality first. Compression second.**
>
> Forge の頭を悪くして軽くするのではなく、必要な品質を維持したまま軽くする。

---

## 1. 「小さいモデル」と「量子化」を区別する

次の2つを同じものとして扱わない。

### A. パラメータ数そのものを減らす

例:

```text
7B model
  ↓
1.5B model
```

これはモデルそのものの規模が変わるため、推論力、意味理解、曖昧な自然文への対応、日本語品質、計画能力、コード生成能力などが低下する可能性がある。

### B. 同じ規模のモデルを量子化する

例:

```text
7B FP16
  ↓
7B 8-bit
  ↓
7B 4-bit
```

モデルのパラメータ数自体は維持しつつ、重みの数値表現を圧縮する。

量子化でも品質低下が起こる可能性はあるため無条件に採用しないが、**7B → 1.5B のようにモデル規模そのものを縮小する方法とは別の最適化手段**として扱う。

---

## 2. Forge の原則

モデル選定では次の優先順位を固定する。

1. Forge Task の品質
2. 意味理解の正確性
3. Schema / structured output の遵守
4. 生成物の Validator 合格率
5. Task success rate
6. 推論 latency
7. RAM / VRAM 使用量
8. Disk 容量
9. Cold start / warm-up 時間

**Disk 容量だけを理由に上位の品質項目を犠牲にしない。**

低資源 PC で小型モデルを候補にしてよいのは、**標準と同一の Forge Task、
生成品質、安全性、Design、Reliability の全 Gate を通過した場合だけ**である。
小型モデルを「低品質モード」として利用者へ提供してはならない。単体で同一基準を
満たせない場合は、Reuse-first、別 Runtime、分割実行、利用者が許可した別の
Execution Host（実行を担当する端末）へ切り替え、成果物の品質を下げない。

---

## 3. 量子化を正式に比較試験する

同一のベースモデルについて、利用可能でライセンス上問題のない範囲で複数の量子化方式を比較する。

候補例:

```text
Base model
├─ higher precision
├─ 8-bit class
└─ 4-bit class
```

特定の bit 数や GGUF quant type を事前に「正解」と固定しない。

Forge Benchmark の実測結果により採否を決める。

---

## 4. Benchmark で必ず測るもの

量子化候補ごとに、最低限次を測定する。

- Model file size
- RAM usage
- VRAM usage（GPU 使用時）
- Cold-start latency
- Warm latency
- tokens/sec 等の推論性能
- JSON / Schema compliance
- 日本語の自然さ
- 意味理解の正確性
- 曖昧性判定の正確性
- 不要な ASK（追加質問）の発生率
- BUILD / ASK / UPDATE 判断精度
- Capability gap 判定精度
- Forge Document 生成成功率
- Validator 合格率
- Repair 回数
- 最終 Task success rate

単純な「返答が出た」「JSON が返った」だけでは品質 PASS としない。

---

## 5. 同じテストセットで比較する

量子化前後を別々の問題で比較しない。

同じ Seed（乱数の再現値）から作った同一の自然文セットを使い、条件をそろえて比較する。

テスト文は固定テンプレートだけにせず、次を含める。

- 日常的な管理ツール
- 業務ツール
- 言い換え
- 曖昧な要求
- 明確な要求
- 既存 Capability だけで成立する要求
- Missing Capability を含む要求
- 日本語特有の省略表現
- 長めの要求
- 複数条件を含む要求

Capability 名や Widget 名をユーザー入力側へ漏らして正解を誘導しない。

---

## 6. 品質劣化の判定

量子化版の容量・速度が優れていても、重要な Forge Benchmark が基準を下回った場合は採用しない。

特に以下の悪化を重く扱う。

- ユーザーの意図を別の問題として解釈する
- ツールへ入力すべきデータ項目を blocking unknown と誤認する
- 本来 BUILD できる依頼で不要な ASK を出す
- Missing Capability を見落とす
- 作れない機能を作れたように見せる
- JSON / Schema 違反が増える
- Validator failure / Repair が増える
- 日本語が不自然になる

これらが明確に悪化する量子化設定は、容量が大幅に減っても標準採用しない。

---

## 7. Reuse-first と併用する

モデルを軽くすることだけで速度・容量問題を解こうとしない。

Forge の基本経路は引き続き Reuse-first とする。

```text
User Need
   ↓
Existing Capability で解決可能？
   ├─ YES → 再利用 / 組み合わせ
   └─ NO  → AI / Planning / Self-extension
```

既存 Capability だけで処理できる場合は、大型 Local Model を毎回呼ばない。

これにより、**高品質モデルを保持したまま、AI を使う回数と待ち時間を減らす**。

---

## 8. モデルは必要時にロードする

高性能モデルを Disk に保持していても、常時 RAM / VRAM に載せる必要はない。

```text
Disk
  └─ Approved high-quality model

通常処理
  → Capability 中心

AI が必要
  → Model load / warm state を利用

一定時間未使用
  → 必要に応じて memory release
```

Disk 容量、RAM 使用量、Runtime latency を別々の問題として扱う。

---

## 9. 配布方式との関係

`FORGE-SELF-CONTAINED-DISTRIBUTION.md` の方針と組み合わせる。

標準 Installer にすべての大型 Model を重複同梱する必要はない。

- Forge 本体と Model を分離する
- Model は必要時に自動取得可能にする
- Offline Bundle では検証済み Model を同梱可能にする
- Model は共有キャッシュに1つだけ保持する
- Forge 本体更新で Model を再ダウンロードしない
- 古い / 未使用 / 重複 Model を安全に整理できるようにする

モデルの配布方式を軽くすることと、モデルの知能を弱くすることを混同しない。

---

## 10. Hardware Profile と Model Profile

将来、PC 性能に応じて Model Profile を選択する場合も、単純に「低性能 PC = 小型モデル」で決めない。

Hardware Profile（端末性能の分類）は**品質の分類ではなく、同一品質へ到達する
実行経路の分類**である。変えてよいのは、内部 Runtime、実行場所、分割方法、
待ち時間（公開上限内）、電力・メモリ使用量だけである。利用者へ渡す意味、機能、
見た目、安全性、Privacy、保存性、Accessibility、Evidence の基準は変えてはならない。

各 Hardware Profile について、Forge Benchmark を満たした Model / Quantization の組み合わせのみ Approved Profile に登録する。

例:

```text
Hardware Profile A
  → 7B 4-bit が品質基準・速度基準を満たす
  → 採用候補

Hardware Profile B
  → 7B 4-bit は遅すぎる
  → 別 Runtime / Quantization / offload を比較
  → それでも不成立なら別の許可済み Execution Host / 分割実行を選ぶ
```

小型モデルへの切替は最初の解決策ではなく、**標準と同じ品質 Evidence を持つ
実行候補**とする。同一 Gate を通らない Profile は Approved にせず、端末別の
品質差を作らない。

---

## 11. 現在の実機 Evidence との関係

2026-09-01 の開発実機では、Qwen2.5 1.5B の単純な structured output が warm 状態で約4秒まで短縮した一方、実際の Forge Conversation 経路では意味判断の誤りと大きな latency が観測された。

この結果から、次を教訓として固定する。

> **速い小型モデルが、そのまま Forge に最適なモデルとは限らない。**

今後は Model の単純速度だけでなく、実際の Forge End-to-End Task で比較する。

---

## 12. 採用 Gate

量子化版を正式採用するには、最低限次を満たすこと。

```text
Same base model
   ↓
Quantized candidate
   ↓
Forge Benchmark
   ├─ Quality PASS
   ├─ Semantic PASS
   ├─ Schema PASS
   ├─ Validator PASS
   ├─ Runtime stability PASS
   └─ Size / latency improvement confirmed
            ↓
         Approved
```

**容量が小さくなっただけでは Approved にしない。**

品質が維持できない場合は、より高精度な量子化、別 Runtime、GPU / CPU 最適化、Reuse-first 強化、モデルのオンデマンド取得・ロードなどを先に検討する。

---

## 13. Product Requirement

Forge の Local AI 最適化は、次の原則に従う。

> **モデル品質を守る。**  
> **量子化は品質を測ってから採用する。**  
> **容量削減のために Forge の知能を意図的に劣化させない。**  
> **高品質モデルを必要なときだけ効率よく使う。**  
> **判断は印象ではなく Evidence / Benchmark で行う。**

同じ要求に対して、PC、GPU、RAM、OS、無料・有料、Local・別Hostの違いを理由に
成果物品質を上下させない。性能差は Execution Resolver（実行経路の選択機構）が
吸収し、全利用者へ同じ Product Quality Contract を適用する。

これは Local Model、Runtime、Installer、Hardware Profile の設計変更時にも維持する。
