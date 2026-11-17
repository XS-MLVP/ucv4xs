"""Legal and corrupt response controls for the extracted RPT-03 checker."""
from types import SimpleNamespace

import pytest

from suites.memblock.mmu.testbenches.ptwrepeater.checker import check_response_payload
from suites.memblock.mmu.testbenches.ptwrepeater.model import response_payload

pytestmark = pytest.mark.selftest


def test_response_payload_preserves_identity_and_rejects_corruption():
    expected = {"tag": 0xABCD, "ppn": 0x34567, "s2xlate": 2}
    assert response_payload(0xABCD, 0x34567, 2) == expected
    for field in expected:
        snap = dict(expected)
        env = SimpleNamespace(response_snapshot=lambda: dict(snap))
        check_response_payload(env, 0xABCD, 0x34567, 2)
        snap[field] ^= 1
        with pytest.raises(AssertionError):
            check_response_payload(env, 0xABCD, 0x34567, 2)
