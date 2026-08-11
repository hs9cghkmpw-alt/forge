"""`backend/app/main.py`の`.env`読み込み(TD35)の回帰テスト。

FORGE-AI-QUALITY-001(2026-08-11)で発見・修正した実バグ: `backend/.env`
(`GETTING_STARTED.md`・`backend/.env.example`が案内する設定場所)に
`GEMINI_API_KEY`を書いても、それを実際に読み込むコードがどこにも
存在しなかった。`requirements.txt`には`python-dotenv`が依存として
既に入っていたが、呼び出し側が無かったため実質的に無意味な状態
だった——利用者が別途OSの環境変数として明示的に`export`した場合のみ
動作する仕様になっていた(ドキュメントはそう案内していない)。

**発見の経緯**: choice_field/bar_chart(TD34)の実機検証中、
「あるDomainのプロンプトは成功するのに、別のプロンプトだけ
『GEMINI_API_KEYが設定されていません』というエラー(実際には`.env`に
キーが存在するのに)で失敗する」という現象を発見した。調査の結果、
household_budget等IR経由の7 Domainは`ForgeLanguageCompiler`が完全に
決定的(Provider呼び出しが一切無い)であるため、キーの有無に関わらず
「成功」していただけで、実際にGeminiへ到達するのは`Compiler.compile()`
(Legacy Domain経由)を通るリクエストだけであり、そちらは`.env`が
読み込まれないため常に失敗していたことが分かった。

**修正**: `main.py`の先頭(他のimportより前)で
`load_dotenv(os.path.join(_BACKEND_DIR, ".env"))`を呼ぶよう追加した。
`load_dotenv()`は既定で既存のOS環境変数を上書きしない(`override=False`)
ため、本番デプロイ環境で実際の環境変数として設定されているケースには
影響しない。

実行方法:
    cd backend
    python -m unittest tests.test_main_env_loading -v
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class TestMainLoadsBackendEnvFile(unittest.TestCase):
    """サブプロセスで検証する理由: `app.main`は既に他のテストモジュールから
    importされている可能性があり(pytestのモジュールキャッシュ)、同一
    プロセス内でreloadすると他のテストへ副作用を及ぼしうる。完全に独立した
    新しいPythonプロセスで、`GEMINI_API_KEY`をOS環境変数としては明示的に
    除去した状態から`app.main`をimportし、実際に`.env`の内容が
    `os.environ`へ反映されることを確認する。"""

    def test_importing_app_main_loads_gemini_api_key_from_dotenv(self) -> None:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(backend_dir, ".env")
        if not os.path.isfile(env_path):
            self.skipTest("backend/.envが存在しない環境(CI等)のため、このテストはスキップする")
        with open(env_path, encoding="utf-8") as f:
            if "GEMINI_API_KEY" not in f.read():
                self.skipTest("backend/.envにGEMINI_API_KEYが無い環境のため、このテストはスキップする")

        env = dict(os.environ)
        env.pop("GEMINI_API_KEY", None)  # OS環境変数としては明示的に「未設定」の状態を作る

        result = subprocess.run(
            [sys.executable, "-c", "import app.main; import os; print('SET' if os.environ.get('GEMINI_API_KEY') else 'UNSET')"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, msg=f"stderr: {result.stderr}")
        self.assertEqual(
            result.stdout.strip(), "SET",
            msg=(
                "app.mainのimportだけではGEMINI_API_KEYがos.environへ反映されなかった"
                f"(TD35の回帰)。stderr: {result.stderr}"
            ),
        )

    def test_load_dotenv_call_targets_the_backend_env_file(self) -> None:
        """`.env`の中身に依存しない、より軽量な回帰テスト: main.pyが
        `load_dotenv()`を、backend/.envの絶対パスで呼び出すコードを
        実際に含んでいることをソースコードレベルで確認する
        (「今後誤ってこの呼び出しを削除・変更してしまう」ことを検出する)。
        """
        here = os.path.dirname(os.path.abspath(__file__))
        main_py_path = os.path.join(here, "..", "app", "main.py")
        with open(main_py_path, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("from dotenv import load_dotenv", source)
        self.assertIn('load_dotenv(os.path.join(_BACKEND_DIR, ".env"))', source)


if __name__ == "__main__":
    unittest.main()
