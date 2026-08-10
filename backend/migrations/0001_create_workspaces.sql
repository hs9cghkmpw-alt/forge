-- FORGE V2 Phase 1 (Workspace Foundation)
-- FORGE-V2-DATABASE-DESIGN-SPECIFICATION.md 4.1節・12章をそのまま実装する。
--
-- 注記(重要、未検証): このスクリプトは実際のSupabase/PostgreSQL環境で
-- 一度も実行できていない(Claudeのサンドボックスにはネットワーク接続
-- された Postgres インスタンスが無いため)。CEO環境のSupabase
-- Migration機構(`supabase migration up` 等)で実行し、実際に
-- テーブル作成・RLS有効化が意図通りに機能するかを確認する必要がある。
--
-- Phase 2以降のテーブル(folders/collections/applications等)は、
-- このMigrationには含めない(絶対条件「Phase 1以外を実装しない」)。

CREATE TABLE workspaces (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id         uuid NOT NULL UNIQUE REFERENCES auth.users(id)
                              ON DELETE CASCADE ON UPDATE CASCADE,
    created_at            timestamptz NOT NULL DEFAULT now(),
    structure_version     integer NOT NULL DEFAULT 1
                              CHECK (structure_version >= 1),
    display_default_view  text NOT NULL DEFAULT 'icon'
                              CHECK (display_default_view IN ('icon', 'list', 'dashboard', 'category', 'timeline'))
);

-- Primary Key・owner_user_idのUNIQUE制約(1 User = 1 Workspace)は、
-- CREATE TABLE内で既に定義済み。追加のIndexは不要
-- (owner_user_idはUNIQUE制約により自動的にIndexが張られる、PostgreSQLの標準挙動)。

-- Row Level Security(FORGE-V2-DATABASE-DESIGN-SPECIFICATION.md 12章)
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;

CREATE POLICY workspace_owner_all ON workspaces
    FOR ALL
    USING (owner_user_id = auth.uid())
    WITH CHECK (owner_user_id = auth.uid());

-- ロールバック手順(Implementation Roadmap9章の「Additive Onlyのため
-- 通常はdownスクリプトの実行は不要」という方針に従い、Migration
-- スクリプト自体の失敗時のみ使う想定):
--
-- DROP POLICY IF EXISTS workspace_owner_all ON workspaces;
-- DROP TABLE IF EXISTS workspaces;
