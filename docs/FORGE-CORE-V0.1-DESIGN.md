# Forge Core v0.1 設計書

**Project:** Forge  
**Status:** DESIGN / PROPOSED  
**作成日:** 2026-09-15  
**対象:** Forge Core（Forgeの最小中核）

---

## 1. この設計書の目的

Forgeの最終目標は、人間が自然な言葉で問題や目的を伝えると、Forgeが意味を理解し、必要な解決方法を考え、実際に使える道具を作り、検証し、会話を通じて改善できる基盤になることである。

最終的にはHardware（ハードウェア）以外の主要ソフトウェア基盤をForge自身が所有する。

そのための最初の実装単位として、Forge Core v0.1を定義する。

Forge Core v0.1は、OS、Compiler、AI、UIを一度に作るものではない。将来のForge Runtime、Language、UI、AI、Appsへ接続できる**最小の意味・構造・実行・検証の土台**を作ることを目的とする。

---

## 2. 上位設計との関係

この設計は以下の上位方針を前提とする。

- Forgeは単なるAIコード生成サービスではない。
- 人間の目的をForgeが理解し、使える道具へ変換する。
- 「生成された」だけでは完成ではない。
- 検証可能な結果を重視する。
- Forgeそのものは開発者が手を動かして理解しながら作る。
- Hardware（ハードウェア）以外の主要ソフトウェア基盤を長期的にForge側で所有する。
- JSON等の構造化された仕様を、AIと実装の間の重要な境界として利用する。
- 実装状態はDESIGNED / PROPOSED / IMPLEMENTED / TESTED / VERIFIED等を明確に分ける。

上位設計ではForgeの流れを

```text
人間の要求
  ↓
AI理解
  ↓
アプリ設計
  ↓
構造化仕様
  ↓
生成
  ↓
検証
  ↓
修正
  ↓
テスト
  ↓
品質評価
  ↓
完成
```

としている。Forge Core v0.1は、このうち特に「構造化仕様」「最小実行」「検証」の基礎をForge自身の設計として確立する。

---

## 3. Forge Core v0.1の役割

Forge Coreは、**Forgeが扱うソフトウェアの最小共通表現と、それを安全に扱う最小実行・検証機構**とする。

最初のCoreは、AIそのものではない。

AIがなくても、手で作った入力からCoreを動かせることを必須条件とする。

```text
入力
 ↓
Core Model（Forge内部モデル）
 ↓
Validation（検証）
 ↓
Execution（実行）
 ↓
Observable Result（観測可能な結果）
```

これにより、AIが生成したものでも人間が作ったものでも、同じCoreで扱える。

---

## 4. v0.1で扱う最小概念

v0.1では概念を増やしすぎない。

### 4.1 Intent（意図）

「何を実現したいのか」を表す。

例：

```text
intent: shopping_list
```

v0.1では自然言語そのものをCoreが理解する必要はない。まず構造化されたIntentをCoreが正しく扱えることを優先する。

### 4.2 Entity（対象）

操作対象となるデータや概念。

例：

```text
entity: item
```

### 4.3 Action（操作）

何をするか。

例：

```text
add
remove
```

### 4.4 State（状態）

実行中に変化する情報。

例：

```text
items: []
```

### 4.5 Data（データ）

Entityが持つ具体的な値。

例：

```text
name: "milk"
quantity: 1
```

### 4.6 Result（結果）

実行後にCoreが観測可能な形で返す結果。

例：

```text
items = [
  { name: "milk", quantity: 1 }
]
```

---

## 5. 最小データモデル

v0.1では、まず以下のような構造を基本形として検討する。

```json
{
  "version": "0.1",
  "intent": "shopping_list",
  "entities": {
    "item": {
      "fields": {
        "name": "string",
        "quantity": "integer"
      }
    }
  },
  "state": {
    "items": []
  },
  "actions": {
    "add": {
      "target": "item"
    },
    "remove": {
      "target": "item"
    }
  }
}
```

これは**最終JSON仕様ではない**。

v0.1では「Coreが何を表現する必要があるか」を検証するための最小候補とする。

実装を開始する前に、この構造が過剰・不足でないかをテストケースから検証する。

---

## 6. v0.1の責務境界

### Forge Coreが担当する

- 構造化された入力の受け取り
- 基本構造の検証
- Entity / State / Actionの整合性確認
- 最小Actionの実行
- Stateの更新
- 結果の返却
- エラーの明示
- 実行結果の再現性確保

### Forge Coreがまだ担当しない

- 自然言語理解
- LLM推論
- 自律Agent
- UI描画
- ネットワーク通信
- データベース
- OS機能
- Compiler
- 高度な型システム
- 自動コード生成
- 本格的なAI学習

これらは将来Coreの上に接続する。

---

## 7. なぜAIを最初から入れないのか

Forgeの製品にはAIが重要だが、Forge Coreの最初の検証にAIを入れると、失敗原因を分離できなくなる。

例えば動作しなかった場合、

- AIが間違えたのか
- 仕様が悪いのか
- CoreのParserが悪いのか
- Runtimeが悪いのか
- State更新が悪いのか

を切り分けにくくなる。

したがってv0.1では、**入力を人間が固定して与え、Coreの決定的（同じ入力なら同じ結果になる）な動作を先に完成させる。**

AIは後から入力生成側に接続する。

---

## 8. 最初の実装対象

最初に作るプログラムは、巨大なFrameworkではなく、以下の最小Coreとする。

```text
Forge Core v0.1
 ├─ Model
 │   ├─ Intent
 │   ├─ Entity
 │   ├─ State
 │   └─ Action
 │
 ├─ Validator
 │
 └─ Executor
      ├─ add
      └─ remove
```

最初の実装では、外部Frameworkに依存しない**小さな単体プログラム**を目標とする。

言語・実行環境は、Pastoral PCで再現可能かつ学習効果が高いものを、実装開始前に確認して決める。

---

## 9. 最初の動作確認

最小テストは次のようにする。

### Test 1 — 空の状態

```text
items = []
```

### Test 2 — add

```text
add("milk", 1)
```

結果：

```text
items = ["milk x1"]
```

### Test 3 — 複数追加

```text
add("bread", 2)
```

結果：

```text
items = ["milk x1", "bread x2"]
```

### Test 4 — remove

```text
remove("milk")
```

結果：

```text
items = ["bread x2"]
```

### Test 5 — 不正操作

存在しないitemをremoveした場合、黙って成功扱いにしない。

```text
Result:
  success = false
  error = explicit error
```

---

## 10. v0.1の成功条件

以下をすべて満たした時点で、Core v0.1を実装済みとする。

1. 構造化入力を読み取れる。
2. 基本構造を検証できる。
3. Actionを実行できる。
4. Stateを正しく更新できる。
5. 不正入力を検出できる。
6. 同じ入力に対して再現可能な結果になる。
7. テストで動作を確認できる。
8. 実装者自身が各処理を説明できる。
9. 外部AIに依存せず動作する。
10. 実装状態とテスト状態をGitHubに記録できる。

---

## 11. 将来への接続

v0.1は小さいが、将来の各層へ接続できるようにする。

```text
                 Forge Apps
                     ↑
                 Forge UI
                     ↑
                  Forge AI
                     ↑
              Forge Runtime
                     ↑
             Forge Core Model
                     ↑
              Forge Language
                     ↑
                 Forge OS
                     ↑
                 Hardware
```

実際の依存関係は今後の設計で変わり得る。特にForge Language、Compiler、Runtime、Core Modelの境界は、v0.1の実装・学習結果をもとに再評価する。

---

## 12. v0.1で意図的にやらないこと

- FlutterでUIを作って「Core完成」としない。
- LLMを接続して「AIが動いたからCore完成」としない。
- Supabase等に保存して「Runtime完成」としない。
- 大量のコードをAIに生成させて理解を省略しない。
- OS開発へ飛び込まない。
- 最終仕様だと決めつけない。

v0.1の目的は、**Forge自身の最小構造を自分の手で理解し、動かし、検証すること**である。

---

## 13. 開発手順

```text
設計レビュー
   ↓
最小テストケース確定
   ↓
実装言語・実行環境決定
   ↓
Model実装
   ↓
Validator実装
   ↓
Executor実装
   ↓
テスト
   ↓
エラー修正
   ↓
再テスト
   ↓
実機環境で確認
   ↓
GitHub記録
```

重要な判断を飛ばして実装を開始しない。

---

## 14. 現在の状態

**DESIGNED / PROPOSED**

まだ実装済みとは扱わない。

次のステップは、この設計書をレビューし、v0.1で本当に必要な最小要素だけを確定することである。
