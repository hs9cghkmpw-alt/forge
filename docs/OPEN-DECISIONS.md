# Forge — いま判断が要ること（2026-08-24 更新）

CEOが作戦を練るための、**未決事項と事実**のまとめ。
このファイルだけ読めば分かるように自己完結させてある。

- 現在のbranch: `claude/forge-master-handoff-k46jns`
- 016A commit A（`50b2c3d`）/ commit B（`fe2664c`）まで実装・push済み
- テスト: backend 1304 / forge_ai 521

---

## 0. 判断してほしいこと（結論だけ先に）

| # | 判断 | 選択肢 |
|---|---|---|
| A | **着手順** | ①P0バグ→Knowledge→デザイン会話 ②P0→デザイン会話→Knowledge ③デザイン会話を最優先 |
| B | **デザインの軸をどこまで増やすか** | 雰囲気 / 何を目立たせるか / 詰め具合 / 色 のどれを対象にするか |
| C | **色をAIに触らせるか** | 触らせない（推奨）／意味の色だけ／自由に |
| D | **latest の意味** | 「最後に追加した行」か「日付が一番新しい行」か（下記 §5） |
| E | **Flutter SDKのバージョン** | CIは3.47.0 / CEO実機は3.44.9。pinするか範囲を決めるか |
| **F** | **🔴 端末を跨いで辿れる仮名IDを持つか**（017 §6） | ①二層化（推奨）②Eventに常に付ける ③持たない（Global Learningを諦める） |

---

## 0-F. 【新規・最重要】仮名IDを持つかどうか（017 §6）

**これは方針の転換なので、黙って進めない。**

### いまのForgeの約束

コードに明文がある（`backend/app/ai/gateway/learning_foundation.py`、
`ExperienceRecord.ref` の説明）:

> セッションIDでも利用者IDでもない、**Store内の位置**である
> （「セッションを跨いで個人を辿れる識別子を持たない」）。
> プロセスを跨いで意味を持たず、記録が捨てられれば無効になる。

生成の記録も、変更の記録も、同じ姿勢で作ってある。
**いまのForgeは「誰が作ったか」を辿れない。** これは事故ではなく設計である。

### 017が要求すること

Growing AI Architecture §5 は `pseudonymous_install_id`（端末を跨いで
同一と分かる仮名ID）を**必須フィールド**にしている。

**必要な理由は正当である。** これが無いと §14 の
「1人が大量のEventを送ってGlobal AIを偏らせるのを防ぐ」が
**原理的に成立しない**（誰が何件送ったか数えられないため）。

### 3つの選択肢

| | 内容 | 得るもの | 失うもの |
|---|---|---|---|
| **① 二層化（推奨）** | ローカルの記録は今のまま識別子なし。**Consentを出して外へ送ると決めたEventにだけ**仮名IDを付ける | Global Learningが成立する。Consent OFFの人の記録は性質が変わらない | 実装が1層増える |
| ② 常に付ける | 全Recordに最初から仮名IDを持たせる | 単純 | **Consentと無関係にローカル記録が「辿れるもの」に変わる**。いまの約束を破る |
| ③ 持たない | 現状維持 | 約束を守る | Global Learningの投稿制限が作れない＝**Poisoning対策が効かない** |

### 私の推奨は①

理由: 017 §9 が「Consent OFFでも基本Forge / Local AI / Personal Memory
が使えること」と要求している。①なら、**Consentを出していない利用者の
体験と記録は、いまと1ミリも変わらない。**

> **「名前を消したから匿名」とは扱わない**（017 §6 自身の言葉）。
> ①でも、外へ出すと決めた分については「仮名で辿れる」ことを
> 隠さずに書く。

### 決まるまで進めないもの

* §14 Poisoning対策の設計（投稿制限が①②③で変わる）
* Learning Event の必須フィールド確定

**決まらなくても進められるもの**: commit C（R1 Hardening）と
commit D（Knowledge/RAG）は、この判断に依存しない。

---

## 1. 「伝えたらデザインを直す」— 現状と、やるべき形

### いまできないこと（コードを読んで確認済み）

会話でアプリを直す経路（`apply_update`）は存在する。しかし**デザインを
知らない**。

* 変更要求と現在のJSON全部をAIへ渡し、**JSON全体を書き直させている**
* プロンプトに `style_role` も Design Language も**一言も出てこない**
  （Widget型とstate型の話だけ）

つまり「もっと落ち着いた感じにして」と言っても、AIは語彙を知らないので
意味の役割を変えられない。しかも全体書き直しなので、**残高のKPIが黙って
消えてもValidatorは気付けない**（Validatorは構造しか見ない）。

これはR1で作った「AIは意味を選ぶ／値は選ばせない」と真逆の方式である。

### やるべき形

会話の言葉を、**Design Languageの軸への択一**へ写す。

```
「もっと落ち着いた感じにして」 → screen_density = relaxed
「一覧を詰めて」               → screen_density = compact
「残高をもっと目立たせて」     → 主KPIの選び直し／強調
「収入を目立たせて」           → finance系の強調
```

この形の利点:

* R1の資産がそのまま効く（語彙・軸ごとの検証・fallback記録・Criticの階層チェック）
* **全体を書き直さないので、残高が消える事故が構造的に起きない**
* 「この言い方には compact が受け入れられた」が、そのままLocal AIの学習素材になる
* AI呼び出しは1回（いまのUPDATEと同じ。追加コストは増えない）

### 足りないもの

**軸が2つしかない。**

```
screen_density : compact / normal / relaxed
list_surface   : card / elevated
```

「落ち着いた感じ」「目立たせて」に答えるには足りない。増やす候補:

| 軸の候補 | 応えられる言葉 | 備考 |
|---|---|---|
| 全体の雰囲気（tone） | 落ち着いた／温かい／元気な | IRに`visual_style`として概念は既にある。会話からは変えられない |
| 何を主KPIにするか | 残高を／収入を／件数を目立たせて | 意味の判断。いまはCompilerが決めている |
| 一覧の並べ方 | カードで／表で／タイルで | `record_list_view.layout`に card/grid が既にある |
| 意味の色 | もっと青っぽく | **一番設計が要る**。値ではなく意味として扱わないと破綻する |

**増やすほどAIが選び間違える余地とRuntimeが保証すべき組み合わせが増える**
（`docs/spec/DESIGN-LANGUAGE-V1.md` §6の増やす条件を通す必要がある）。

---

## 2. 016 の未着手分 — P0バグ4件（実害あり）

前回の指示書 FORGE-R2-KNOWLEDGE-RAG-AND-R1-HARDENING-016 の内容。
**まだ1行も実装していない**（前回の応答がAPI 529 Overloadedで着手前に中断）。

### P0-1. Design Criticが画面をまたいで数えている

`metric.primary`（一番大事な数値）は1つだけ、というルールを
**Document全体で**数えている。

将来こうなったときに誤って落ちる:

```
画面A  保存ボタン = button.primary
画面B  登録ボタン = button.primary   ← 正常なのにblockingになる
```

**画面ごとに数える**のが正しい。いまは単一画面しか作らないので実害は
出ていないが、複数画面へ進む前に直す必要がある。

### P0-2. 「支出＝エラー」の誤判定

`finance.*` と `state.*` が同じDocumentに**1つずつでもあれば**衝突と
判定している。しかし:

```
収入 finance.income / 支出 finance.expense / 同期成功 state.success
```

これは正常。検出したいのは「支出をエラーの赤で表す」ような**意味の
取り違え**であって、共存そのものではない。

### P0-3. AIが決めた「数値の意味」が保存時に消える（実害が一番大きい）

EntitySynthesizerに「全項目が任意なら最初の1つを必須にする」処理が
あり、そこでFieldを組み直している。**そのとき `measure` をコピーして
いない。**

```
AI:  amount / number / measure=additive / required=false
             ↓ 必須へ補正
実際: amount / number / measure=unknown  / required=true
```

R1で追加した「足せる量かどうか」が失われ、**Hero KPIが出なくなる**。
手作業でフィールドをコピーする方式をやめる（`dataclasses.replace`等）。

### P0-4. Golden E2E が会話から始まっていない

いまのE2Eは `/generate` から始まっている。本来の道は

```
User → /converse → Need Model → BUILD → Pipeline → Compiler → Validator → Evidence
```

`/converse` から始める本物のE2Eが無い。

---

## 3. 016 の未着手分 — R2 Forge Knowledge / RAG

**目的**: Forge固有の知識（語彙・仕様）を、Cloud AIとLocal AIが
**同じものを**参照できる形にする。

要点:

* 既存のSource of Truth（Design Language / Measure Semantics /
  Capability Registry）から**変換して**作る。
  Markdownへ手書きコピーして二重管理しない
* CloudだけRAGあり／LocalだけRAGなし、を作らない。
  **Providerを決める前にForge側で知識を解決する**
* 作るだけでなく `design_intent` と `entity_synthesis` へ**実際に渡す**
* Evidenceには**IDだけ**残す（生テキストも利用者の発話も保存しない）
* 古い仕様をAIへ教えないための version / active / deprecated
* RAGは参考資料であって、Truthは Validator / Runtime のまま

**この機能は「伝えたらデザインを直す」と直結する。** AIが語彙を知って
いれば「落ち着いた感じ→relaxed」の精度が上がる。だから
Knowledge→デザイン会話 の順を推奨した。

---

## 4. お金・時間の制約（判断材料）

| 制約 | 実測 | 影響 |
|---|---|---|
| Gemini無料枠 | **1日20回/Model**（429の本文で確認） | 検証だけで尽きる。実運用に足りない |
| Curated生成のAI呼び出し | 0回 → **1回**（TD70） | Design Intentを入れた副作用。推奨解は「Local AIへ寄せる」 |
| OpenAIキー | 受領済みだが**無料枠なし**（前払いクレジット制） | 使うなら有料。要失効・再発行 |
| 2つ目の無料枠 | 未取得 | Groq / Cerebras / OpenRouter のいずれか |
| Flutter SDK | この作業環境に**無い** | 見た目の確認はCI頼み。TD74（壊して落ちるかの確認ができない） |

---

## 5. 設計として曖昧なまま残っている点

### latest（最新値）の意味

`MeasureSemantics.LEVEL`（体温・体重・残高）は「最新値」を出す。
いまの実装は**最後に追加された行**である。

```
8/18のデータを追加 → その後 8/17のデータを追加
→ 「最新」は 8/17 の行になる
```

「追加順の最後」と「日付が一番新しい」は違う。**この意味を確定してから
でないとKnowledgeへ書けない**（曖昧なまま教えると、AIがその曖昧さを学ぶ）。

### コントラスト

Light/Darkで色が違うこと・Darkを明るくすることはテスト済み。しかし
**コントラスト比そのものは測っていない**。「Dark対応」と
「読みやすさの保証」は別物である。

---

## 6. 抱えている技術的負債（主なもの）

| # | 内容 |
|---|---|
| TD41/TD64 | Experience/Generationが永続化されない（再起動で消える） |
| TD51 | Local AI実モデル実行が**0回** |
| TD65 | Runtime結果・利用者の承認が戻る経路が無い（閉ループの最重要の辺） |
| TD66 | Gemini枠の合計値・単位が未検証 |
| TD67 | 第二Cloudが実API未検証（配線はTest Doubleで確認済み） |
| TD70 | CuratedのAI呼び出しが1回増えた |
| TD71 | Widget追加のたびにテスト側の複製switchを直し忘れてCIが落ちる（3回目） |
| TD73 | roleの反映はWidgetごとの対応が要る（1箇所で被せれば効く、は成立しない） |
| TD74 | **Flutter側の配線破壊試験ができていない**（テストが効いているか未確認） |

---

## 7. 参考: いま生成される画面

「家計簿をつけたい」から生成される画面の再現図（実際のDocumentと
実際のスタイル値から起こしたもの。Flutterのスクリーンショットではない）:

https://claude.ai/code/artifact/3ccc697a-13d9-4f93-922f-874ec705551c

---

## 7.5 CEOから来た新方針（2026-08-18）

「伝えたらデザインを直す」が**最優先方針**になった。7分類すべてを
最終的に対象とし、優先順位は

1. 情報階層・強調 → 2. レイアウト/余白/密度 → 3. コンポーネントの見せ方
→ 4. Semantic Color / Theme → 5. タイポグラフィ → 6. 細かな装飾
→ 7. アニメーション・遷移

これは見た目の便利機能ではなく、

```
User Correction → Revision Evidence → Forge Knowledge → Local AI Improvement
```

を閉じる経路として設計する。設計案は
**`docs/spec/DESIGN-REVISION-PROPOSAL.md`**、016の状態整理は
**`docs/tasks/FORGE-016-STATE.md`**。

---

## 8. 参照

| 文書 | 内容 |
|---|---|
| `docs/HANDOFF.md` | 最新の申し送り（毎回更新） |
| `docs/reports/FORGE-R1-CLOSURE-015-report.md` | R1完了時の全項目 |
| `docs/spec/DESIGN-LANGUAGE-V1.md` | 33 roleの語彙 |
| `docs/spec/METRIC-SEMANTICS-V1.md` | 数値が「どういう量か」 |
| `docs/PRODUCT-DIRECTION.md` | **最上位方針（変更不可）** |
| `TECH_DEBT.md` | 技術的負債 TD1〜TD74 |
