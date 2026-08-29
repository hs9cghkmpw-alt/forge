"""**一部しか出来ていないものを「出来た」として学習させない**（020A3B §5）。

The legacy string list and typed capability evidence must both preserve the boundary
between fully implemented, partial, and missing capabilities. Regression examples use
capabilities that are *currently* partial/missing rather than freezing historical gaps
that Forge has since implemented.
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

PARTIAL_NEED = "旅行の写真を日付ごとに残してメモを付けたい"
# Interactive audio mixing is implemented; *authoring/exporting a newly composed
# asset* is intentionally still a real critical gap (`effect.media_compose`).
MISSING_NEED = "植物を育てながら新しい音を合成して書き出すゲームを作りたい"
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
        self.assertNotIn("data.photo", record.capabilities)

    def test_a_missing_capability_is_not_listed_bare(self) -> None:
        record = _record_for(MISSING_NEED)
        self.assertIn("unsupported:effect.media_compose", record.capabilities)
        self.assertNotIn("effect.media_compose", record.capabilities)

    def test_no_id_appears_both_bare_and_qualified(self) -> None:
        for need in (PARTIAL_NEED, MISSING_NEED, CLEAN_NEED):
            record = _record_for(need)
            bare = {c for c in record.capabilities if ":" not in c}
            qualified = {c.split(":", 1)[1] for c in record.capabilities if ":" in c}
            with self.subTest(need=need):
                self.assertEqual(bare & qualified, set())

    def test_fully_implemented_capabilities_are_still_listed_bare(self) -> None:
        record = _record_for(CLEAN_NEED)
        self.assertIn("view.list", record.capabilities)
        self.assertIn("view.metric", record.capabilities)


class TestTypedUsageIsTheSourceOfTruth(unittest.TestCase):
    def test_the_typed_evidence_states_the_status_in_a_field(self) -> None:
        record = _record_for(PARTIAL_NEED)
        photo = next(u for u in record.capability_usage if u.capability_id == "data.photo")
        self.assertIs(photo.status, CapabilityUsageStatus.PARTIAL)
        self.assertTrue(photo.requested)
        self.assertFalse(photo.used_successfully)

    def test_a_missing_capability_is_requested_but_not_used(self) -> None:
        record = _record_for(MISSING_NEED)
        compose = next(
            u for u in record.capability_usage
            if u.capability_id == "effect.media_compose"
        )
        self.assertTrue(compose.requested)
        self.assertFalse(compose.used)
        self.assertIs(compose.status, CapabilityUsageStatus.MISSING)

    def test_training_candidates_can_tell_partial_from_implemented(self) -> None:
        record = _record_for(PARTIAL_NEED)
        succeeded = {
            u.capability_id for u in record.capability_usage if u.used_successfully
        }
        self.assertNotIn("data.photo", succeeded)
        self.assertIn("view.list", succeeded)

    def test_the_legacy_list_is_documented_as_superseded(self) -> None:
        source = (
            _ROOT / "backend" / "app" / "ai" / "gateway" / "generation_evidence.py"
        ).read_text(encoding="utf-8")
        self.assertIn("capability_usage", source)
        self.assertIn("Source of Truth", source)


if __name__ == "__main__":
    unittest.main()
