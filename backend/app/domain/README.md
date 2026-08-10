# domain/

**Clean ArchitectureにおけるBackendの中心。フレームワーク非依存。**
FastAPI・Supabase SDKなど外部技術への参照を一切持たない、純粋なPythonのみで構成する。

- `entities/` — ビジネスルールを表す純粋なデータクラス（Pydantic Modelでも可だが外部I/Oを持たない）
- `repositories/` — リポジトリの**インターフェース**（`abc.ABC` / `Protocol`）。実装は持たない
- `usecases/` — 1ユースケース = 1クラス（or 関数）。entitiesとrepositoriesのインターフェースのみに依存する

## 依存ルール

```
routers → usecases → repositories(interface, domain) ← repositories(実装, infrastructure)
                 ↓
              entities
```

- `usecases/` は `repositories/` の**インターフェース**にのみ依存し、具象実装（`app/repositories/`）を知らない。
- 具象実装（`app/repositories/` = infrastructure層）が `domain/repositories/` のインターフェースを実装し、
  `core/di.py` で束縛する。
- `services/` は複数usecaseを跨ぐ調整や、外部API呼び出し（AI等）を伴う**アプリケーション層**として、
  usecaseの「上」に位置づける（例: `AppGenerationService` が `GenerateUiSchemaUseCase` を呼ぶ）。

## なぜ既存の `services/` `repositories/` を残したまま `domain/` を追加したか

Task001時点の `services/repositories/models/schemas` はレイヤードアーキテクチャとして機能していたが、
「ビジネスルールの中心」と「外部技術への依存」が同居しやすい構成だった。
`domain/` を追加することで、
- `entities`（純粋な業務データ）
- `repositories`（契約=interface）
- `usecases`（業務ロジック）
を外部技術から完全に独立させ、テスト容易性と将来のDB/AI基盤差し替え耐性を高める。
既存の `repositories/` はこの `domain/repositories/` の**実装置き場（infrastructure）**として役割を再定義する。
