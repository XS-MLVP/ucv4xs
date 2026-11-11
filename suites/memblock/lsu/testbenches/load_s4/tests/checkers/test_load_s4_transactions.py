"""Payload/checker controls for the LoadUnitS4 transaction adapter.

A corrupted expectation must fail at the identity checker; an unknown or
overflowing payload field must be rejected before a native write.  Selftest
only, not hardware functional credit.
"""
import pytest

from suites.memblock.lsu.testbenches.load_s4.env import LoadS4Env
from suites.memblock.lsu.testbenches.load_s4.transactions import S4HeadPayload
from suites.memblock.lsu.testbenches.load_s4.transactions import blank_payload

pytestmark = pytest.mark.selftest


def test_payload_rejects_unknown_and_overflowing_fields():
    payload = blank_payload()
    with pytest.raises(KeyError, match="unknown"):
        payload.with_field("not_a_field", 1)
    with pytest.raises(ValueError, match="vaddr"):
        payload.with_field("vaddr", 1 << 50)
    with pytest.raises(ValueError, match="hasException"):
        S4HeadPayload(hasException=2)


def test_identity_checker_rejects_a_changed_field(dut_factory):
    env = LoadS4Env(dut_factory("load_s4"))
    payload = blank_payload().with_field("paddr", 0x1234)
    env.drive(1, payload)
    env.dut.Step(1)
    corrupted = payload.with_field("paddr", 0x1235)
    with pytest.raises(AssertionError, match="paddr"):
        env.check(1, corrupted, "corrupted expectation")


def test_valid_flag_boundary_is_rejected_before_a_native_write(dut_factory):
    env = LoadS4Env(dut_factory("load_s4"))
    with pytest.raises(ValueError, match="valid must be 0 or 1"):
        env.evaluate(2, blank_payload(), "bad valid")
    with pytest.raises(ValueError, match="valid must be 0 or 1"):
        env.check(2, blank_payload(), "bad valid")
