# Forge 外部境界・自作化マップ

**作成日:** 2026-09-15  
**状態:** 長期設計台帳・修正版  
**対象:** Forge プロジェクト

---

## 1. 目的

Forgeの最終目標は、**既存ハードウェアだけを外部に残し、それ以外のソフトウェア基盤をForge自身で作れる状態へ到達すること**である。

現在は開発を進めるために既存OS、Flutter、Python等の既存技術を利用する場合がある。しかし、それらは最終的なForgeの所有基盤ではなく、開発途中の足場・比較対象・学習対象として扱う。

この文書では、

- 現在どの既存技術を足場として利用しているか
- それがForgeのどの層に関係するか
- 将来Forge自身が何を作るか
- 最終的に外部へ残すものは何か
- 自作化をどの順序で進めるか

を一つの地図として管理する。

---

## 2. 最上位方針

> **最終的に外部に残すのはハードウェア。ソフトウェア基盤はForge自身で作る。**

開発初期には既存ソフトウェアを利用してよい。ただし、利用することと最終的に依存し続けることは区別する。

```text
既存技術を利用
      ↓
仕組みを理解
      ↓
Forge独自の設計・実装を作る
      ↓
Forge側の実装範囲を広げる
      ↓
既存ソフトウェアへの依存を段階的に外す
      ↓
Forge自身のソフトウェア基盤へ
```

これは「何でもゼロから今すぐ作る」という意味ではない。**長期的にForge自身がソフトウェア基盤を所有するための移行戦略**である。

---

## 3. 現在から最終形への大地図

```text
【現在】

既存ハードウェア
      │
      ▼
既存OS・既存開発環境
      │
      ├── Flutter / Material 3 / Riverpod
      ├── FastAPI
      ├── Supabase
      ├── Ollama / 外部AIモデル
      ├── Python等
      └── その他の既存ソフトウェア
             │
             ▼
        現在のForge
        ├── Forge Apps
        ├── Forge UI / JSON UI
        ├── Forge Document
        ├── Forge Runtime
        ├── Forge AI
        └── 検証・生成・修復基盤

                    │
                    │  学習・理解・自作化
                    ▼

【中間】

既存ハードウェア
      │
      ▼
既存OS（必要な範囲で開発用に利用）
      │
      ▼
Forge独自ソフトウェア層を拡大
      ├── Forge Runtime
      ├── Forge Language / Compiler
      ├── Forge UI
      ├── Forge AI
      └── Forge Apps

                    │
                    │  さらに自作範囲を拡大
                    ▼

【長期目標】

既存ハードウェア
      │
      ▼
Forge OS
 ├── Kernel
 ├── Process / Memory Management
 ├── Driver Layer
 ├── Device / I/O
 ├── Filesystem
 ├── Network Stack
 ├── Security Model
 └── Graphics
      │
      ▼
Forge Runtime
 ├── Forge Language
 ├── Compiler
 ├── Standard Library
 ├── Package System
 ├── App Runtime
 └── Forge Document / UI Runtime
      │
      ▼
Forge AI
 ├── AI基盤
 ├── Tensor Engine
 ├── 推論・生成基盤
 ├── 安全な実行境界
 └── 能力生成・検証・再利用
      │
      ▼
Forge Apps
 └── 人間の要求から高品質・検証済みアプリを構築
```

---

## 4. 現在の既存技術と将来のForge自作対象

| 現在利用している既存技術 | 現在の役割 | 将来のForge側対象 | 最終的な扱い |
|---|---|---|---|
| Flutter | 現在のUI・アプリ開発基盤 | Forge UI / UI Runtime | Forge独自基盤へ移行 |
| Material 3 | 現在のUI設計・部品 | Forge Design System | Forge独自の設計体系へ |
| Riverpod | 現在の状態管理 | Forge Runtime / State Model | Forge独自モデルへ |
| FastAPI | 現在のAPI・バックエンド | Forge Runtime / Service基盤 | Forge独自基盤へ |
| Supabase | 現在のDB・認証等 | Forge Data / Storage / Security | Forge独自基盤へ |
| Python | 開発・AI・検証等 | Forge Tooling / Runtime等 | 必要範囲をForge側へ移行 |
| Ollama | 現在のローカルAI実行 | Forge AI Runtime | Forge独自AI実行基盤へ |
| 外部AIモデル | 現在のAI能力 | Forge AI | Forge AI自身の基盤・モデル運用へ発展 |
| 既存OS | 現在の開発・実行環境 | Forge OS | 最終的にForge OSへ |
| 既存Filesystem | 現在のファイル保存 | Forge Filesystem | 最終的にForge側へ |
| 既存Network Stack | 現在の通信基盤 | Forge Network Stack | 最終的にForge側へ |
| 既存Driver | 現在のハードウェア制御 | Forge Driver Layer | 最終的にForge側へ |
| 既存Graphics | 現在の描画基盤 | Forge Graphics | 最終的にForge側へ |

### 重要な区別

上表の既存技術は、**最終的にForgeが依存し続ける外部ソフトウェア一覧ではない**。

現在の開発を可能にする足場として利用しているものであり、長期目標ではForge自身のソフトウェア基盤へ置き換える対象である。

---

## 5. 最終的にForge自身が所有する主要レイヤー

### A. Forge Apps

人間の要求から作られるアプリケーション。

品質目標は単なるプロトタイプではなく、**アプリストア上位を狙える水準**。

### B. Forge UI

画面、操作、状態、アクセシビリティ、デザイン言語等をForge側で扱う層。

### C. Forge AI

推論・生成だけでなく、知識、記憶、ツール、評価、検証、能力生成・再利用等を含むForgeの知能基盤。

### D. Forge Runtime

Forgeで作られたプログラムを実行する基盤。

### E. Forge Language

Forge自身のプログラム表現。

### F. Forge Compiler

Forge Languageを実行可能な形へ変換する仕組み。

### G. Forge Standard Library

基本データ型、入出力、文字列、コレクション、時間、ファイル等の共通機能。

### H. Forge Package System

機能の配布・再利用・依存関係管理。

### I. Forge OS

Kernel、メモリ・プロセス管理、Driver、Filesystem、Network、Security、Graphics、I/O等。

---

## 6. 自作化の順序（暫定）

具体的な実装順序は、各層の依存関係を実際に調査した上で確定する。

### Phase 0 — 現状把握

- 現在のForge実装を保存
- 現在の既存ソフトウェア依存を一覧化
- 各依存がForgeのどの層に存在するかを確認
- 現在の実証済み機能と未検証機能を分離

### Phase 1 — 最小Forge基盤

- Forge独自の最小データモデル
- 最小実行モデル
- 最小UI / Documentモデル
- 最小テスト・検証ループ

### Phase 2 — Forge Runtime

- 実行モデル
- 状態管理
- データモデル
- 基本I/O
- Runtime API

### Phase 3 — Forge Language / Compiler

- 最小言語仕様
- Lexer（字句解析）
- Parser（構文解析）
- AST（抽象構文木）
- Interpreter / VM（インタプリタ / 仮想マシン）
- Compiler
- Standard Library

### Phase 4 — Forge UI / App Runtime

- UIモデル
- レイアウト
- イベント
- 状態
- ナビゲーション
- アクセシビリティ
- アプリパッケージ化

### Phase 5 — Forge AI

- 推論境界
- Tool実行境界
- 記憶
- 評価
- 能力生成・再利用
- Tensor Engine等の自前基盤化

### Phase 6 — Forge OS

依存関係を確認しながら、必要最小限のOS層から開始する。

- Kernel
- メモリ管理
- プロセス管理
- Driver
- I/O
- Filesystem
- Network Stack
- Security
- Graphics

### Final — Forgeソフトウェア基盤の自給化

既存ソフトウェアへの依存を一括で排除するのではなく、Forge自身の代替実装が成立した部分から段階的に移行する。

最終的な外部境界は**既存ハードウェア**とする。

---

## 7. 最終的に外部に残すもの

### 原則として外部に残すもの

- CPU
- メモリ
- ストレージ
- GPU
- ディスプレイ
- キーボード・マウス等の入力機器
- その他の物理ハードウェア

つまり、**物理的なコンピュータ資源は既存ハードウェアを利用する。**

### 最終的なForge自作対象

- OSの中核
- Runtime
- Language
- Compiler
- Standard Library
- Package System
- UI実行基盤
- AI実行基盤
- データ・状態モデル
- 検証・品質保証基盤
- その他Forgeを構成するソフトウェア基盤

GitHub等の外部サービスは、Forgeそのものの実行基盤ではなく、**開発・記録・共同作業のための外部インフラ**として別扱いにする。

---

## 8. 品質原則

自作化によって品質を下げることは禁止する。

Forge独自実装へ移行する際も、少なくとも以下を維持・向上させる。

- 正確性
- 安定性
- セキュリティ
- プライバシー
- アクセシビリティ
- 再現性
- テスト可能性
- 保守性
- ユーザー体験
- アプリ生成品質

特に、Forgeが生成するアプリは「自作だから低品質でよい」とはしない。

**最終的にアプリストア上位を狙える品質水準を維持する。**

---

## 9. 開発ループ

```text
設計
 ↓
自分でコードを書く
 ↓
実行
 ↓
テスト / 実機確認
 ↓
失敗・問題の記録
 ↓
原因を理解
 ↓
修正
 ↓
再テスト
 ↓
GitHubへコミット
 ↓
次の最小単位へ進む
```

AIは調査・設計補助・レビュー・デバッグ・文書化に利用するが、重要な仕組みをブラックボックス化しない。

---

## 10. 現時点の次の作業

この地図を基準として、次に以下を調査する。

1. 現在のリポジトリ内で既存ソフトウェアが実際にどこで使われているか確認する。
2. 既存Forge実装のうち、将来のForge自作基盤へ引き継げる概念を特定する。
3. 各Forgeレイヤー間の依存関係を確定する。
4. 最初に手作業で実装する最小Forgeコアを決める。
5. その実装・検証・学習結果をGitHubへ記録する。

**まだOSやCompilerをいきなり作り始めない。まず現在地と依存関係を正確に把握し、最小単位から進める。**
