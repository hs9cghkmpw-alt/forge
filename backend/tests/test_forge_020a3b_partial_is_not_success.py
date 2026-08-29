"""**一部しか出来ていないものを「出来た」として学習させない**（020A3B §5）。

---

## 何が起きていたか

「旅行の写真を日付ごとに残してメモを付けたい」の Evidence は、
`GenerationRecord.capabilities` に**両方**を持っていた。

```
data.photo           ← 素の ID
partial:data.photo
```

`data.photo` は PARTIAL である——**写真そのものは扱えない。**
ファイル名やメモを文字として残しているだけである。

素の ID しか読まない利用者（Dataset Builder、Local AI の学習）は、
これを**実装済みの成功例**として読む。**Forge が自分の限界を
学べなくなる**どころか、出来ないことを出来ると学習する。

## 直し方

素の ID は「**全部出来て、実際に使った**」の意味に限る。
`partial:` / `unsupported:` が付く ID は、素の形では入れない。

## 本来の Source of Truth

`capabilities`（文字列の並び）は R4 以前からある古い契約である。
**新しい Source of Truth は `capability_usage`**（typed）であり、
`requested` / `used` / `status` / `source` を欄で持つ。

Dataset Builder は**こちらを読むこと**。ここで固定する。
"""

from __future__ import annotations

import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app.ai.gateway.capability_evidence import CapabilityUsageStatus  # noqa: E402
from app.ai.gateway.generation_evidence import default_generation_store  # noqa: E402
from app.main import app  # noqa: E402

#: `data.photo` が PARTIAL になる Need。
PARTIAL_NEED = "旅行の写真を日付ごとに残してメモを付けたい"
#: critical missing を持つ Need。
MISSING_NEED = "釣った場所を地図に残して魚の種類を記録したい"
#: 全部 IMPLEMENTED で済む Need。
CLEAN_NEED = "毎日の収入と支出を記録して残高を見たい"


def _record_for(need: str):  # noqa: ANN201
    client = TestClient(app)
    response = client.post(
        "/api/v1/ai/generate",
        json={"input": {"natural_language": need,
                        "generation_options": {"provider": "mock"}}},
    )
    assert response.status_code == 200, response.text
    return default_generation_store().all_records()[-1]


class TestPartialNeverLooksLikeFullSuccess(unittest.TestCase):
    def test_a_partial_capability_is_not_listed_bare(self) -> None:
        record = _record_for(PARTIAL_NEED)
        self.assertIn("partial:data.photo", record.capabilities)
        self.assertNotIn(
            "data.photo", record.capabilities,
            "PARTIAL が素の ID でも入っている。"
            " 素の並びだけを読む利用者が『写真を扱えた』と学習する",
        )

    def test_a_missing_capability_is_not_listed_bare(self) -> None:
        record = _record_for(MISSING_NEED)
        self.assertIn("unsupported:view.map", record.capabilities)
        self.assertNotIn("view.map", record.capabilities)

    def test_no_id_appears_both_bare_and_qualified(self) -> None:
        """**一般の不変条件。** Need を足しても成り立つこと。"""
        for need in (PARTIAL_NEED, MISSING_NEED, CLEAN_NEED):
            record = _record_for(need)
            bare = {c for c in record.capabilities if ":" not in c}
            qualified = {c.split(":", 1)[1] for c in record.capabilities if ":" in c}
            with self.subTest(need=need):
                self.assertEqual(
                    bare & qualified, set(),
                    "同じ ID が素と修飾つきの両方で入っている",
                )

    def test_fully_implemented_capabilities_are_still_listed_bare(self) -> None:
        """弾きすぎない。**出来たものは素で残る。**"""
        record = _record_for(CLEAN_NEED)
        self.assertIn("view.list", record.capabilities)
        self.assertIn("view.metric", record.capabilities)


class TestTypedUsageIsTheSourceOfTruth(unittest.TestCase):
    """**新しい契約は `capability_usage` である。**"""

    def test_the_typed_evidence_states_the_status_in_a_field(self) -> None:
        record = _record_for(PARTIAL_NEED)
        photo = next(
            u for u in record.capability_usage if u.capability_id == "data.photo"
        )
        self.assertIs(photo.status, CapabilityUsageStatus.PARTIAL)
        self.assertTrue(photo.requested)
        # **文字列の接頭辞を読ませない。** 欄で言う。
        self.assertFalse(
            photo.used_successfully,
            "PARTIAL が『成功として使えた』になっている",
        )

    def test_a_missing_capability_is_requested_but_not_used(self) -> None:
        record = _record_for(MISSING_NEED)
        missing_view = next(
            u for u in record.capability_usage if u.capability_id == "view.map"
        )
        self.assertTrue(missing_view.requested)
        self.assertFalse(missing_view.used)
        self.assertIs(missing_view.status, CapabilityUsageStatus.MISSING)

    def test_training_candidates_can_tell_partial_from_implemented(self) -> None:
        """Dataset Builder が**接頭辞を parse せずに**判別できること。

        これが出来ないなら、typed evidence は置物である。
        """
        record = _record_for(PARTIAL_NEED)
        succeeded = {
            u.capability_id for u in record.capability_usage if u.used_successfully
        }
        self.assertNotIn("data.photo", succeeded)
        self.assertIn("view.list", succeeded)

    def test_the_legacy_list_is_documented_as_superseded(self) -> None:
        """**将来 Dataset Builder が読む先**を文書で固定する。

        コメントが消えたら落ちる。「typed が正である」と誰も知らない
        まま、古い並びを読む実装が入るのを防ぐ。
        """
        source = (
            _ROOT / "backend" / "app" / "ai" / "gateway" / "generation_evidence.py"
        ).read_text(encoding="utf-8")
        self.assertIn("capability_usage", source)
        self.assertIn(
            "Source of Truth", source,
            "どちらが正なのかが `generation_evidence.py` に書かれていない",
        )


if __name__ == "__main__":
    unittest.main()
