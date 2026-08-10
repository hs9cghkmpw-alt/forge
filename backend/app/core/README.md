# core/

Backend全レイヤーが依存してよい唯一のインフラ層。逆にここは
`domain/` `services/` `routers/` `ai/` `plugins/` のいずれにも依存してはならない。

- `config.py`（今後追加） — 環境変数・設定値の一元管理（Pydantic Settings）
- `di.py`（今後追加） — DIコンテナ（domainのinterfaceにinfrastructureの実装を束縛する）
- `security.py`（今後追加） — JWT検証・認可の共通ロジック
- `exceptions.py`（今後追加） — 共通例外クラス（`middleware/`で統一レスポンスに変換）

Flutter側 `frontend/lib/core/` と役割は対称（縦の土台）。
