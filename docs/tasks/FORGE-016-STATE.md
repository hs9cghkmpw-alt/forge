# FORGE-016 の状態と、完了可能な単位への分割

**2026-08-18 / 中断中。実装は1行も入っていない。**

---

## 1. いまの状態（事実）

```
branch : claude/forge-master-handoff-k46jns
HEAD   : 0911450（R1完了の edb2bd7 + 文書2件のみ）
実装    : 016 は未着手
理由    : 前回の応答が API 529 Overloaded で着手前に中断
```

**押し忘れではない。** 書き始める前に落ちたので、失われた作業も無い。
独立監査の `ahead_by=0 / changed files=0` は正しい状態だった。

現在のテスト・CIは **R1完了時のまま健全**:

```
backend 1258 passed / forge_ai 521 passed / Flutter 508 passed
flutter analyze 0件 / build web 成功 / CI 全4 job green
```

---

## 2. 完了可能な単位への分割

016は「P0バグ4件 + R2 Knowledge/RAG」という大きな塊だった。
**1つずつ独立してcommit・push・CIまで到達できる単位**へ割り直す。

各単位は「これだけやって止めても、Forgeが壊れない・意味が通る」形に
してある。

### 単位 1 — MeasureSemantics 消失バグ（最優先・最小）

**実害が一番大きく、修正は一番小さい。**

EntitySynthesizerの「全項目が任意なら最初を必須にする」処理で
Fieldを組み直す際、`measure` をコピーしていない。

```
AI:  amount / number / measure=additive / required=false
             ↓ 必須へ補正
実際: amount / number / measure=unknown  / required=true
```

R1で入れた「足せる量か」が失われ、**Hero KPI（残高など）が出なくなる**。

* 直し方: 手作業のフィールドコピーをやめ、`dataclasses.replace` 等へ
* テスト: 全MeasureSemanticsについて、required補正後も保持されること
* 破壊試験: copyを外す → preservation test が落ちる
* 見積: 小

> **他のどの作業より先に入れるべき。** 意味が保存時に消える状態のまま
> 上へ機能を積むと、後から原因が分からなくなる。

### 単位 2 — Semantic Design Critic を画面単位へ

「一番大事な数値は1つ」をDocument全体で数えている。
複数画面へ進む前に直す。

* 変更: 集計を screen 単位へ。Evidence も screen 別を持てる形へ
* テスト: 1画面に2つ→FAIL / 2画面に1つずつ→PASS
* 破壊試験: Document全体集計へ戻す → multi-screen test が落ちる
* 見積: 小〜中
* **いまは単一画面しか作らないので実害は出ていない**

### 単位 3 — finance / state の誤判定

`finance.*` と `state.*` が1つずつでもあれば衝突としている。
収入・支出・同期成功が並ぶのは正常。

* 変更: 「同じWidget / 同じ対象への役割の取り違え」を見る形へ
* テスト: 別Widgetでの共存→PASS / 支出をstate.dangerで表す→FAIL
* 破壊試験: 共存をconflictへ戻す → valid finance test が落ちる
* 見積: 小〜中

### 単位 4 — /converse から始まる Golden E2E

いまのE2Eは `/generate` から。本来の道は

```
User → /converse → Need Model → BUILD → Pipeline → Compiler → Validator → Evidence
```

* AIはTest Doubleでよい。差し替えるのは**AI応答だけ**
* 見積: 中
* 単位1〜3のどれとも独立に入れられる

### 単位 5 — R2 Forge Knowledge（土台）

既存のSource of Truth から KnowledgeEntry へ**変換**する層。
Markdownへ手書きコピーして二重管理しない。

* 対象: Design Language / Measure Semantics / Capability Registry
* 契約: id / kind / version / status / supersedes / training_use
* version・active/deprecated（古い仕様をAIへ教えない）
* 見積: 中
* **この単位だけでは本番から呼ばれない**（次の単位6とセットで意味を持つ）

### 単位 6 — Knowledge を本番へ接続

* `design_intent` へ Design Language Knowledge
* `entity_synthesis` へ Measure / Capability Knowledge
* **Provider を決める前に**Forge側で解決する（Cloud/Localで同じもの）
* Evidence には **IDだけ**残す（生テキストも発話も保存しない）
* 破壊試験: 各接続を外す → Production wiring test が落ちる
* 見積: 中
* **単位5と必ずセットで完了させる。** 5だけで止めると
  「作ったが呼ばれない」（Forgeが4回繰り返した失敗）になる

### 単位 7 — Local route への接続確認

Local実モデルが動かなくても、**Local Provider path へ
KnowledgeContext が渡ること**はTest Doubleで確認できる。

* 「Local modelを実行できなかったのでRAGとLocalの配線も未実装」は不可
* ただし**実Local model generation は未検証と明記する**
* 見積: 小

---

## 3. 依存関係

```
単位1 ──┐
単位2 ──┼─→ 互いに独立。どれからでも入れられる
単位3 ──┤
単位4 ──┘

単位5 ──→ 単位6（必ずセット）──→ 単位7
```

**単位1だけは先行を強く推奨**（意味が消える状態で上へ積まない）。

---

## 4. 各単位の完了条件（共通）

CEO指示により、以下を満たすまで完了扱いにしない。

1. commit SHA
2. remote branch への push
3. GitHub上でHEADが変わったこと
4. changed files
5. tests（backend / forge_ai / Flutter）
6. CI 全4 job green
7. 配線破壊試験（外したら落ちることの確認）
8. docs更新（HANDOFF / CHANGELOG / TECH_DEBT / report）

**pushされていない実装は、存在しないものとして扱う。**

---

## 5. 「伝えたらデザインを直す」との関係

CEOから新しい最優先方針が来ている（`docs/spec/DESIGN-REVISION-PROPOSAL.md`）。

016との関係:

| 016の単位 | Design Revision への効き方 |
|---|---|
| 単位1（measure消失） | **前提**。意味が消える状態でRevisionを載せない |
| 単位2（画面単位Critic） | 直した結果の検査に効く |
| 単位3（finance誤判定） | 「赤が強すぎる」を扱うときに効く |
| 単位4（/converse E2E） | Revisionも会話から入るので、道が同じ |
| 単位5・6（Knowledge） | **精度に効くが必須ではない**。use_when を知るほど当たる |

つまり **016を捨てる必要は無く、そのまま Design Revision の土台になる**。

---

## 6. 参照

| 文書 | 内容 |
|---|---|
| `docs/OPEN-DECISIONS.md` | 判断待ちの一覧・制約・技術的負債 |
| `docs/spec/DESIGN-REVISION-PROPOSAL.md` | 「伝えたら直る」の設計案 |
| `docs/HANDOFF.md` | 最新の申し送り |
