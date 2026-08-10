"""`backend/migrations/0002_create_folders.sql`の静的検証
(FORGE V2 Phase 2 Step 1)。

**重要な注記**: このサンドボックスには実際に接続されたPostgreSQL/
Supabaseインスタンスが無いため、Migrationを実際に実行して検証する
ことはできない(`0001_create_workspaces.sql`と同じ制限)。この
テストは、SQLファイルの**テキスト内容**が、Database Design
Specification通りの要素(必須カラム・FK・CHECK制約・RLS Policy)を
含んでいることを、文字列検索で確認するに留める。実際の`CREATE
TABLE`文法・制約の妥当性は、CEO環境で`supabase migration up`(または
同等のPostgreSQLクライアント)を使って検証する必要がある。
"""

from __future__ import annotations

import os
import unittest

_MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "migrations", "0002_create_folders.sql"
)


class TestFoldersMigrationContent(unittest.TestCase):
    def setUp(self) -> None:
        with open(_MIGRATION_PATH, encoding="utf-8") as f:
            self.sql = f.read()

    def test_creates_the_folders_table(self) -> None:
        self.assertIn("CREATE TABLE folders", self.sql)

    def test_has_all_required_columns(self) -> None:
        for column in ("id", "workspace_id", "parent_folder_id", "name", "created_at"):
            self.assertIn(column, self.sql, f"必須カラム'{column}'が見つからない")

    def test_id_is_primary_key_with_uuid_default(self) -> None:
        self.assertIn("PRIMARY KEY DEFAULT gen_random_uuid()", self.sql)

    def test_workspace_id_references_workspaces_with_cascade(self) -> None:
        self.assertIn("REFERENCES workspaces(id)", self.sql)
        self.assertIn("ON DELETE CASCADE", self.sql)

    def test_parent_folder_id_is_self_referencing_with_restrict(self) -> None:
        self.assertIn("REFERENCES folders(id)", self.sql)
        self.assertIn("ON DELETE RESTRICT", self.sql)

    def test_name_has_non_empty_check_constraint(self) -> None:
        self.assertIn("CHECK (length(name) > 0)", self.sql)

    def test_has_composite_index_on_workspace_and_parent(self) -> None:
        self.assertIn("CREATE INDEX idx_folders_workspace_parent ON folders (workspace_id, parent_folder_id)", self.sql)

    def test_rls_is_enabled(self) -> None:
        self.assertIn("ALTER TABLE folders ENABLE ROW LEVEL SECURITY", self.sql)

    def test_rls_policy_restricts_to_owner(self) -> None:
        """RLS確認(CEO指示の必須ケース)。実際のDB上での動作確認は
        できないが、Policyの条件式が`owner_user_id = auth.uid()`を
        参照していることを、SQLテキスト上で確認する(Database Design
        Specification12章のPolicy定義と一致することの裏付け)。"""
        self.assertIn("CREATE POLICY folder_owner_all ON folders", self.sql)
        self.assertIn("owner_user_id = auth.uid()", self.sql)
        # USING句・WITH CHECK句の両方に同じ条件があること
        # (読み取りだけでなく書き込みも制限することの確認)。
        using_and_check_count = self.sql.count("owner_user_id = auth.uid()")
        self.assertEqual(using_and_check_count, 2, "USING句とWITH CHECK句の両方に条件があること")

    def test_does_not_reference_applications_table(self) -> None:
        """絶対条件「Applicationは実装しない」の確認。folders
        Migrationが、まだ存在しないapplicationsテーブルへの実際の
        SQL参照(REFERENCES句・CREATE TABLE)を持たないことを検証する。

        単純な文字列"applications"の有無だけで判定すると、このSQL
        ファイル自身の説明コメント(「Application関連は...実装しない」
        という注記)にも"applications"という語が含まれるため、
        誤って失敗する(実際に発生し、修正した経緯がある)。実行可能な
        SQL文としての参照(`REFERENCES applications`・`CREATE TABLE
        applications`)が無いことを、コメント行を除外した上で確認する。
        """
        executable_lines = [line for line in self.sql.splitlines() if not line.strip().startswith("--")]
        executable_sql = "\n".join(executable_lines).lower()
        self.assertNotIn("references applications", executable_sql)
        self.assertNotIn("create table applications", executable_sql)

    def test_does_not_reference_collections_table(self) -> None:
        """絶対条件「Collectionは実装しない」の確認。同上の理由で
        コメント行を除外して判定する。"""
        executable_lines = [line for line in self.sql.splitlines() if not line.strip().startswith("--")]
        executable_sql = "\n".join(executable_lines).lower()
        self.assertNotIn("references collections", executable_sql)
        self.assertNotIn("create table collections", executable_sql)

    def test_has_rollback_instructions(self) -> None:
        self.assertIn("DROP TABLE IF EXISTS folders", self.sql)


if __name__ == "__main__":
    unittest.main()
