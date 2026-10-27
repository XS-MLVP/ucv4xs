"""Negative self-tests of verification helpers, not replacement RTL DUTs."""
import pytest

from mmuverify.common.checks import check_l2_success
from mmuverify.l2.l2pf import PFModel


def clean():
    return dict(valid=1, s2xlate=0, s1_v=1, s1_pf=0, s1_af=0,
                s1_ppn=0x123, s1_tag=0x456, s2_gpf=0, s2_gaf=0)


@pytest.mark.parametrize("field,bad", [
    ("valid", 0), ("s1_v", 0), ("s1_pf", 1), ("s1_af", 1),
    ("s1_ppn", 0), ("s1_tag", 0), ("s2xlate", 1),
])
def test_success_checker_rejects_mutations(field, bad):
    snap = clean()
    check_l2_success(snap, ppn=0x123, tag=0x456, stage=0)
    snap[field] = bad
    with pytest.raises(AssertionError):
        check_l2_success(snap, ppn=0x123, tag=0x456, stage=0)


@pytest.mark.parametrize("field", ["s2_gpf", "s2_gaf"])
def test_allstage_checker_rejects_guest_fault(field):
    snap = clean()
    snap["s2xlate"] = 3
    snap[field] = 1
    with pytest.raises(AssertionError):
        check_l2_success(snap, stage=3)


def test_success_checker_rejects_missing_field():
    snap = clean()
    del snap["s1_af"]
    with pytest.raises(AssertionError):
        check_l2_success(snap)


def test_prefetch_model_can_consume_after_flush():
    model = PFModel()
    model.step(0, 0, 0, True)
    model.step(1, 0x10000, 0, False)
    model.step(0, 0, 1, False)
    assert model.history == [0x10008, None, None, None]
    assert model.valid == 0


def test_page_memory_root_leaf_is_at_root():
    from mmuverify.l2.l2tlb import PageMemory, pte
    mem = PageMemory()
    mem.build_sv39(0x80000, 0x12345, 0x40000, level=2)
    word = mem.read(0x80000000)
    assert word == pte(0x40000, r=1, w=1, x=1, u=1, a=1, d=1)
    assert mem.read(0x80001000) == 0


def test_static_audit_detects_shadowing_and_discarded_response(tmp_path):
    from tools.audit_cases import audit
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_bad.py").write_text(
        "async def test_same():\n    assert True\n"
        "async def test_same():\n    await env.wait_resp()\n")
    result = audit(tmp_path)
    assert result["status"] == "FAIL"
    assert any("duplicate" in item for item in result["failures"])
    assert any("constant assertion" in item for item in result["failures"])
    assert any("discarded response" in item for item in result["failures"])
