# Forge 外部依存・自作化マップ

**作成日:** 2026-09-15  
**状態:** 初版・長期設計台帳  
**対象:** Forge プロジェクト

---

## 1. 目的

Forgeは、現在の既存技術を捨てずに利用しながら、時間をかけてForge自身の実装範囲を広げるハイブリッド型の長期プロジェクトとする。

この文書では、

- 現在どの外部技術に依存しているか
- その外部技術がForgeのどの層に関係するか
- 将来的にForge側で何を自作・置換するか
- 何を最後まで外部に残すか
- どの順序で自給化を進めるか

を一つの地図として管理する。

「外部技術を使っていること」を失敗とは扱わない。外部技術は、ブートストラップ（立ち上げの土台）、比較対象、学習対象として利用する。

---

## 2. 最上位方針

> **外部技術を使う → 仕組みを理解する → Forge独自の抽象化・実装を作る → Forge側の実装範囲を広げる → 必要に応じて低レイヤーまで自作する。**

ハードウェアそのものは、当面および長期目標において外部に残す。

---

## 3. 現在から最終形への大地図

```text
【現在】既存技術を利用したForge

Hardware（既存PC等）
        │
        ▼
Existing OS（既存OS）
        │
        ├── Flutter / Material 3 / Riverpod
        ├── FastAPI
        ├── Supabase
        ├── Ollama / 外部AIモデル
        ├── Python等
        └── GitHub等
                │
                ▼
        現在のForge
        ├── Forge Apps
        ├── Forge UI / JSON UI
        ├── Forge Document
        ├── Forge Runtime
        ├── Forge AI
        └── 検証・生成・修復基盤

                    ↓
          理解・抽象化・自作化
                    ↓

【中間】Forge独自層を増やす

Hardware（既存）
        │
        ▼
Existing OS（必要な範囲で利用）
        │
        ▼
Forge Runtime
Forge Language / Compiler
Forge UI
Forge AI
Forge Apps
        │
        └── 外部依存を段階的に縮小

                    ↓

【長期目標】Forge自給度を高める

Hardware（外部）
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

## 4. 外部依存 → Forge自作化マップ

| 現在の外部技術・仕組み | 現在の役割 | 将来のForge側対象 | 自作化の方向 | 優先度 |
|---|---|---|---|---|
| Flutter | UI・アプリ実行の現在の土台 | Forge UI / UI Runtime | Forge独自UI実行基盤へ段階移行 | 中〜高 |
| Material 3 | UI設計・コンポーネント | Forge Design System | Forge独自デザイン言語・部品体系へ発展 | 中 |
| Riverpod | 状態管理 | Forge Runtime / State Model | Forge独自状態・データフローへ段階移行 | 中 |
| FastAPI | バックエンド/API | Forge Runtime / Network境界 | Forgeサービス実行基盤へ段階移行 | 中 |
| Supabase | DB・認証・バックエンド基盤 | Forge Data / Storage / Security | Forge独自データ・認証・保存層へ段階移行 | 中〜高 |
| Python | 開発・AI・検証用基盤 | Forge Tooling / Runtime | すぐ全置換せず、必要部分からForge側へ移す | 低〜中 |
| Ollama | ローカルAI実行 | Forge AI Runtime | Forge AI実行境界・モデル管理基盤へ | 中〜高 |
| 外部AIモデル | 推論・生成能力 | Forge AI | モデル依存を減らし、Forge AI基盤・評価・再利用を強化 | 高 |
| GitHub | ソース・設計・履歴管理 | Forge開発基盤 | 長期記録として継続利用 | 置換対象外（当面） |
| 既存OS | 現在の実行環境 | Forge OS | Kernelから段階的に自作 | 高（長期） |
| 既存Filesystem | ファイル保存 | Forge Filesystem | 独自Filesystemへ | 長期 |
| 既存Network Stack | 通信 | Forge Network Stack | 独自ネットワーク層へ | 長期 |
| 既存Driver | ハードウェア制御 | Forge Driver Layer | 必要デバイスから段階実装 | 長期 |
| 既存Graphics | 描画・表示 | Forge Graphics | 独自描画基盤へ | 長期 |

※ この表は「今すぐ置換する一覧」ではない。長期的な自給化対象を管理する地図である。

---

## 5. Forge自身が最終的に所有する主要レイヤー

### A. Forge Apps

人間の要求から作られるアプリケーション。

品質目標は単なるプロトタイプではなく、アプリストア上位を狙える水準。

### B. Forge UI

画面、操作、状態、アクセシビリティ、デザイン言語等をForge側で扱う層。

### C. Forge AI

推論・生成だけでなく、知識、記憶、ツール、評価、検証、能力生成・再利用等を含むForgeの知能基盤。

### D. Forge Runtime

Forgeで作られたプログラムを実行する基盤。

### E. Forge Language

Forge自身のプログラム表現。

### F. Forge Compiler

Forge Languageを実行可能な形式へ変換する仕組み。

### G. Forge Standard Library

基本データ型、入出力、文字列、コレクション、時間、ファイル等の共通機能。

### H. Forge Package System

機能の配布・再利用・依存関係管理。

### I. Forge OS

Kernel、メモリ・プロセス管理、Driver、Filesystem、Network、Security、Graphics、I/O等。

---

## 6. 自作化の順序（暫定）

具体的な実装順序は、各層の依存関係を検証した上で確定する。

### Phase 0 — 現状把握

- 現在のForge実装を保存
- 外部依存を一覧化
- 各依存がどの層に存在するかを確認
- 現在の実証済み機能と未検証機能を分離

### Phase 1 — 最小Forge基盤

- Forge独自の最小データモデル
- 最小実行モデル
- 最小UI/Documentモデル
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

### Final — 自給度の向上

外部依存を一括排除するのではなく、Forge自身で代替可能になった部分から段階的に置換する。

---

## 7. 「外部に残すもの」と「自作するもの」

### 外部に残す

- CPU
- メモリ
- ストレージ等の物理ハードウェア
- 当面の開発PC
- GitHub（長期記録・共同開発基盤として）
- その他、置換する合理性がない外部サービス

### 原則としてForge側へ移す対象

- OSの中核
- Runtime
- Language
- Compiler
- Standard Library
- Package System
- UI実行基盤
- AI実行基盤
- 重要なデータ・状態モデル
- Forge固有の検証・品質保証基盤

※ 「何でも自作」が目的ではない。Forgeの独立性、理解可能性、品質、長期維持性を高めることが目的。

---

## 8. 品質原則

自作化によって品質を下げることは禁止する。

外部技術からForge独自実装へ移行する際も、少なくとも以下を維持・向上させる。

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

1. 現在のリポジトリ内で各外部技術が実際にどこで使われているか確認する。
2. 既存Forge実装のうち、将来の自作基盤へそのまま引き継げる概念を特定する。
3. 各レイヤー間の依存関係を確定する。
4. 最初に手作業で実装する最小Forgeコアを決める。
5. その実装・検証・学習結果をGitHubへ記録する。

**まだOSやCompilerをいきなり作り始めない。まず依存関係を正確に把握し、最小単位から進める。**
