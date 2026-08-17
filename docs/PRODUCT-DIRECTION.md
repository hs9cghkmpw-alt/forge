# Forge Product Direction（変更不可）

CEO提示 2026-08-14。**この方針は個別タスクより上位である。**
実装上の都合によって変更・縮小・先送りしてはいけない。

`docs/ROADMAP.md`（全体方針）・`docs/ROADMAP-TO-TARGET.md`（完成図までの
段取り）は、いずれもこの文書に従属する。矛盾した場合はこちらが勝つ。

---

## 1. 最終目標

Forgeは、

* 自然言語でユーザーの意図を理解し
* 高品質な実用アプリを生成し
* 利用・修正・評価から**Forge自身が継続的に改善する**

システムである。次の2軸を**同時に**進める。

### 軸A — Generated App Quality

生成されるアプリを「動くAI生成UI」ではなく、**美しく・情報設計が優れ・
UXが自然で・実用でき・一般公開しても試作品に見えない**製品品質へ
引き上げる。

Golden App / 完成イメージは**固定テンプレートではなく、Forgeが満たすべき
品質基準**である。

### 軸B — Forge-owned Local AI

Forge固有の知識・評価・経験を持つLocal AIを育てる。目標は
「Local Modelを使うこと」**ではない**。

    Forge Knowledge + Retrieval/RAG + User Feedback
    + Validator Evidence + Runtime Evidence + Visual Quality Evidence
    + Benchmark + Dataset + LoRA/Adapter

によって、Local AIが Forge Language / Capability / Design Language を
理解し、**高品質なアプリを自力生成できるTask領域を継続的に増やす**。

---

## 2. 2つの軸を分離しない

**Visual Quality改善とLocal AI改善は別々のロードマップではない。**
次の閉ループとして設計する。

```
User Need
  ↓
Forge AI / Local AI
  ↓
Capability / Design Language
  ↓
Forge Language
  ↓
Validator
  ↓
Runtime
  ↓
Rendered Application
  ↓
User Acceptance / Correction
  + Runtime Evidence
  + Visual Quality Evidence
  ↓
Experience
  ↓
Knowledge / Dataset Candidate
  ↓
RAG / Local AI Improvement
  ↓
Benchmark
  ↓
Task単位で Local Routing へ昇格
```

ロードマップを書くときは、**この輪のどこを閉じるのか**を必ず示す。
「UIのPhase」と「Local AIのPhase」を別立てにしてはならない。

---

## 3. Design Languageの意味

Design Token / Semantic Style / Component Variant の整備は
**単なる見た目改善ではない。**

Local AIが

    font-size 36px、#23D18B

のような細かい値を毎回推論しなくても、

    metric.primary
    finance.income
    finance.expense
    surface.elevated
    text.secondary

という**意味的表現を選ぶだけ**で、Forge Runtimeが高品質なUIを保証できる
ようにするためである。

> **AIは意味を決める。Forgeは品質を保証する。**

この分担は、Local AIを**小さく・安く・高品質**にするために重要である。
したがってTokenは「色の一覧」ではなく**AIが選ぶ語彙**として設計する。

---

## 4. Golden AppsをTemplate化しない

家計簿・Wellness・Task Manager等のGolden Appは
**この形をコピーするためのTemplateではない。**

目的は、**未知のアプリにも一般化できる Capability / Design Language /
Composition 能力**を評価することである。

* Golden Appへの過学習は禁止
* 有限Template選択システムへの退化は禁止

---

## 5. Cloud AIの位置付け

Cloud Providerの出力は **Teacher Candidate であって Truth ではない。**

正しさ・品質の根拠は可能な限り次の組み合わせで判断する。

* User ACCEPTED
* User CORRECTED
* Validator
* Runtime success
* Structured output validity
* Visual quality evidence
* Held-out benchmark

**Cloudの回答をそのままLocal AIへ模倣学習させない。**

---

## 6. Local AIを後回しにしない

「まずUIを完成させてからLocal AI」という**無期限の先送りは禁止**。

Design LanguageやCapabilityが安定した部分から、
Knowledge → Retrieval → Experience → Benchmark へ順次接続する。

ただし、**仕様が不安定な部分を急いでWeight Trainingして古い仕様を
焼き込むことも避ける。**

### 優先順位

1. Forge-owned Knowledge / RAG
2. Experience / Evidence collection
3. Shadow evaluation
4. Curated Dataset
5. LoRA / Adapter
6. Benchmark による Promotion

---

## 7. Definition of Done

新しい Style / Widget / Capability / AI機能 は、
**「コードが存在する」だけでは完成ではない。**

必要に応じて

    Schema + Compiler + Validator + Runtime
    + Conversation + AI Knowledge + E2E

まで **Production Path** へ到達して初めて Done である。

とくに次を完成扱いしてはならない。

* Runtime にはあるが **Compiler が生成しない**
* Knowledge はあるが **Local AI が参照しない**
* ExperienceStore はあるが **Production から記録されない**

> Forgeはこの3つを**すべて実際に踏んでいる**。
> `transform.aggregate`（Runtime実装済み・Compiler未出力）、
> `ModelGateway`（TD59）、`classify_correction`（007 §10）、
> `ExperienceStore`（TD64）。したがってこれは抽象的な戒めではなく、
> **繰り返している具体的な失敗**である。

---

## 8. 毎回の自己監査

変更の最終報告前に、**必ず7問すべてに答える**。

1. この変更は生成アプリの品質を上げるか
2. この変更はLocal AIが将来学習・利用できる構造になっているか
3. 片方を改善するためにもう片方を後退させていないか
4. Template依存を増やしていないか
5. Production Pathへ本当に接続されているか
6. Local AI改善へ利用できるEvidenceが残るか
7. 実装都合でForgeの最終目標を縮小していないか

**どれかに問題がある場合、黙って目標を変更せず、問題・代替案・
Trade-offを報告する。**
