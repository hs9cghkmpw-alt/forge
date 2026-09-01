"""**出荷する登録表は空であること**（2026-09-01、CI を落とした実バグ）。

---

## 何が起きたか

CI run 33469325234 の `flutter test` が 48 件落ちた。

```text
lib/json_ui/acquired/acquired_registrations.g.dart:10:8:
  Error when reading 'lib/json_ui/acquired/view_calendar/forge_binding.dart':
  No such file or directory
```

原因は生成側ではない。**回帰確認のために E2E を走らせたまま commit した**
ことである。E2E は獲得能力を install して登録表を書き換える。獲得した
Dart 本体は `.gitignore` で除外されているが、**登録表だけは出荷状態を
commit する**設計なので、

* 手元 … 能力あり + 登録表が能力を指す → 通る
* 新しい checkout … 能力なし + 登録表が能力を指す → **コンパイル不能**

という食い違いが生まれた。

## なぜテストで守るのか

「commit 前に restore するのを忘れない」は**忘れる**。実際に忘れた。
機械が見れば忘れない。

このテストは Python 側の job で走る。あちらは install を一度もしないので、
**commit されている状態そのもの**を検査できる。手元で E2E を走らせたまま
`pytest` を回すと落ちる——それが正しい。restore を促す合図である。
"""

from __future__ import annotations

import pathlib
import re
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

REGISTRATIONS = (
    _ROOT / "frontend" / "lib" / "json_ui" / "acquired"
    / "acquired_registrations.g.dart"
)

_IMPORT = re.compile(r"^import '([^']+)'", re.MULTILINE)
_REGISTER = re.compile(r"^\s*registerAcquiredCapability\(", re.MULTILINE)


class TestTheShippedRegistrationTableIsEmpty(unittest.TestCase):
    """**獲得物を commit しない。** 出荷物と生成物の区別を消さない。"""

    def setUp(self) -> None:
        self.assertTrue(REGISTRATIONS.is_file(), f"{REGISTRATIONS} が無い")
        self.body = REGISTRATIONS.read_text(encoding="utf-8")

    def test_it_registers_nothing(self) -> None:
        found = _REGISTER.findall(self.body)
        self.assertEqual(
            found, [],
            "獲得した Capability を指したまま commit されている。\n"
            "`python3 scripts/reuse_first_e2e.py --restore` を実行すること。\n"
            "獲得物は CI が毎回作り直すので、commit してはならない。",
        )

    def test_every_import_target_exists(self) -> None:
        """指している先が**実在すること**。CI が落ちたのはここである。"""
        missing = [
            target for target in _IMPORT.findall(self.body)
            if not (REGISTRATIONS.parent / target).is_file()
        ]
        self.assertEqual(
            missing, [],
            f"登録表が存在しないファイルを指している: {missing}\n"
            "新しい checkout ではコンパイルできない。",
        )

    def test_no_acquired_capability_directory_is_committed(self) -> None:
        """獲得物のディレクトリ自体が残っていないこと。"""
        stray = sorted(
            entry.name for entry in REGISTRATIONS.parent.iterdir()
            if entry.is_dir()
        )
        self.assertEqual(
            stray, [],
            f"獲得した Capability が置かれたままである: {stray}\n"
            "`python3 scripts/reuse_first_e2e.py --restore` を実行すること。",
        )


if __name__ == "__main__":
    unittest.main()
