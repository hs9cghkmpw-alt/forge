-- FORGE V2 Phase 2 Step 1 (Folder)
-- FORGE-V2-DATABASE-DESIGN-SPECIFICATION.md 4.2節・6章・7章・12章を
-- そのまま実装する。
--
-- 注記(重要、未検証): 0001_create_workspaces.sqlと同じ制限(実際の
-- Supabase/PostgreSQL環境で一度も実行できていない)。CEO環境での
-- 検証が必要。
--
-- Application関連(applications.folder_id等)はPhase 3まで存在しない
-- ため、このMigrationには一切含めない(絶対条件「Applicationは実装
-- しない」)。

CREATE TABLE folders (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       uuid NOT NULL REFERENCES workspaces(id)
                           ON DELETE CASCADE ON UPDATE CASCADE,
    name               text NOT NULL CHECK (length(name) > 0),
    parent_folder_id   uuid NULL REFERENCES folders(id)
                           ON DELETE RESTRICT ON UPDATE CASCADE,
    created_at         timestamptz NOT NULL DEFAULT now()
);

-- Index(FORGE-V2-DATABASE-DESIGN-SPECIFICATION.md 7章)
CREATE INDEX idx_folders_workspace_parent ON folders (workspace_id, parent_folder_id);

-- Row Level Security(12章)
ALTER TABLE folders ENABLE ROW LEVEL SECURITY;

CREATE POLICY folder_owner_all ON folders
    FOR ALL
    USING (
        workspace_id IN (SELECT id FROM workspaces WHERE owner_user_id = auth.uid())
    )
    WITH CHECK (
        workspace_id IN (SELECT id FROM workspaces WHERE owner_user_id = auth.uid())
    );

-- ロールバック手順(Migration失敗時のみ想定):
--
-- DROP POLICY IF EXISTS folder_owner_all ON folders;
-- DROP INDEX IF EXISTS idx_folders_workspace_parent;
-- DROP TABLE IF EXISTS folders;
