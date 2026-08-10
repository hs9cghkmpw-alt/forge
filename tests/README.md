# tests/

Frontend/Backendを横断するE2E・統合テスト。
（各アプリ内の単体テストは `frontend/test/` `backend/tests/` に置く）

- `e2e/` — 実際のユーザーフローを模したエンドツーエンドテスト
- `integration/` — 複数サービス（FastAPI + Supabase等）を跨ぐ統合テスト
