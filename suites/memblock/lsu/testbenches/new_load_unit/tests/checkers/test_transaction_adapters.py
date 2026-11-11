"""Input/monitor controls for the NewLoadUnit transaction adapter.

These tests prove that illegal identities are rejected before a native write,
that a missing output pin cannot be silently skipped, and that the full-pin
reference checker still fails when its expected value is corrupted.  They are
selftests and carry no hardware functional credit.
"""
import pytest

from suites.memblock.lsu.testbenches.new_load_unit.env import LoadParentEnv
from suites.memblock.lsu.testbenches.new_load_unit.env.monitor import PIN_NAMES
from suites.memblock.lsu.testbenches.new_load_unit.env.monitor import check_pin_inventory
from suites.memblock.lsu.testbenches.new_load_unit.env.monitor import decode_snapshot
from suites.memblock.lsu.testbenches.new_load_unit.env.stimulus import blank_inputs
from suites.memblock.lsu.testbenches.new_load_unit.env.stimulus import to_inputs
from suites.memblock.lsu.testbenches.new_load_unit.env.stimulus import validate_input_keys
from suites.memblock.lsu.testbenches.new_load_unit.transactions import CycleInput
from suites.memblock.lsu.testbenches.new_load_unit.transactions import DcacheControls
from suites.memblock.lsu.testbenches.new_load_unit.transactions import LoadIssue
from suites.memblock.lsu.testbenches.new_load_unit.transactions import LqTag
from suites.memblock.lsu.testbenches.new_load_unit.transactions import NukeQuery
from suites.memblock.lsu.testbenches.new_load_unit.transactions import Redirect
from suites.memblock.lsu.testbenches.new_load_unit.transactions import RobTag
from suites.memblock.lsu.testbenches.new_load_unit.transactions import SqTag
from suites.memblock.lsu.testbenches.new_load_unit.transactions import TriggerSettings
from suites.memblock.lsu.testbenches.new_load_unit.transactions import TriggerSlot

pytestmark = pytest.mark.selftest


def test_out_of_range_transaction_identity_is_rejected():
    with pytest.raises(ValueError, match="rob.value"):
        RobTag(value=256)
    with pytest.raises(ValueError, match="sq.value"):
        SqTag(value=64)
    with pytest.raises(ValueError, match="lq.value"):
        LqTag(value=128)
    with pytest.raises(ValueError, match="load.address"):
        LoadIssue(address=1 << 64, rob=RobTag())
    with pytest.raises(ValueError, match="nuke.mask"):
        NukeQuery(mask=1 << 16)
    with pytest.raises(ValueError, match="trigger settings require four"):
        TriggerSettings(configs=(), enables=(1, 0))
    with pytest.raises(TypeError, match="LoadIssue"):
        CycleInput.idle().issue(object())
    with pytest.raises(ValueError, match="nuke slot"):
        CycleInput.idle().with_nuke(2, NukeQuery())


def test_representative_single_bit_and_nested_inputs_are_rejected():
    with pytest.raises(ValueError, match="dcache.ready"):
        DcacheControls(ready=2)
    with pytest.raises(ValueError, match="dcache.bank_conflict"):
        DcacheControls(bank_conflict=2)
    with pytest.raises(ValueError, match="load.rf_wen"):
        LoadIssue(address=0x8000_0000, rob=RobTag(), rf_wen=2)
    with pytest.raises(ValueError, match="load.store_set_hit"):
        LoadIssue(address=0x8000_0000, rob=RobTag(), store_set_hit=2)
    with pytest.raises(ValueError, match="redirect.valid"):
        Redirect(valid=2)
    with pytest.raises(ValueError, match="nuke.valid"):
        NukeQuery(valid=2)
    with pytest.raises(ValueError, match="cycle.ldld_check"):
        CycleInput(ldld_check=2)
    with pytest.raises(ValueError, match=r"trigger.enables\[0\]"):
        TriggerSettings(enables=[2, 0, 0, 0])
    with pytest.raises(TypeError, match="load.rob"):
        LoadIssue(address=0x8000_0000, rob=object())
    with pytest.raises(TypeError, match="nuke.rob"):
        NukeQuery(rob=object())
    with pytest.raises(TypeError, match=r"cycle.nuke\[1\]"):
        CycleInput(nuke=(NukeQuery(), object()))
    with pytest.raises(TypeError, match="cycle.dcache"):
        CycleInput(dcache="ready")
    with pytest.raises(TypeError, match=r"trigger.configs\[1\]"):
        TriggerSettings(
            configs=[TriggerSlot(), object(), TriggerSlot(), TriggerSlot()])


def test_default_trigger_settings_encode_a_complete_idle_trigger():
    plan = CycleInput.idle().with_trigger(TriggerSettings())
    encoded = to_inputs(plan)
    validate_input_keys(encoded, blank_inputs())
    trigger = encoded["trigger"]
    assert len(trigger["configs"]) == 4
    assert [cfg.tdata2 for cfg in trigger["configs"]] == [0, 0, 0, 0]
    assert trigger["enables"] == [0, 0, 0, 0]
    assert trigger["debugMode"] == 0
    assert trigger["canRaiseBpExp"] == 1
    defaults = blank_inputs()["trigger"]
    assert [(c.match_type, c.select, c.timing, c.action, c.chain, c.store,
             c.tdata2) for c in trigger["configs"]] == \
        [(c.match_type, c.select, c.timing, c.action, c.chain, c.store,
          c.tdata2) for c in defaults["configs"]]


def _encoded(plan):
    """Encode a plan with trigger slots normalised to comparable tuples."""
    encoded = to_inputs(plan)
    encoded["trigger"]["configs"] = [
        (c.match_type, c.select, c.timing, c.action, c.chain, c.store, c.tdata2)
        for c in encoded["trigger"]["configs"]]
    return encoded


def test_caller_container_mutation_does_not_change_a_constructed_plan():
    nukes = [NukeQuery(), NukeQuery()]
    configs = [TriggerSlot() for _ in range(4)]
    enables = [0, 0, 0, 0]
    plan = CycleInput(nuke=nukes,
                      trigger=TriggerSettings(configs=configs, enables=enables))
    before = _encoded(plan)
    nukes[0] = NukeQuery(valid=True, paddr=0x1234)
    configs[0] = TriggerSlot(tdata2=0xDEAD)
    enables[0] = 1
    after = _encoded(plan)
    assert before == after
    assert plan.nuke[0] == NukeQuery()
    assert plan.trigger.configs[0] == TriggerSlot()
    assert plan.trigger.enables == (0, 0, 0, 0)
    from dataclasses import FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        plan.trigger.configs[0].tdata2 = 1


def test_monitor_rejects_a_missing_output_pin():
    complete = {name: 0 for name in PIN_NAMES}
    del complete["io_cancel"]
    with pytest.raises(KeyError, match="io_cancel"):
        decode_snapshot(complete)
    with pytest.raises(RuntimeError, match="inventory"):
        check_pin_inventory(set(PIN_NAMES) - {"io_cancel"})


def test_corrupted_reference_output_is_rejected_by_the_full_pin_checker(dut_factory):
    env = LoadParentEnv(dut_factory("new_load_unit"))
    env.reset()
    env.prime()
    original = env._model.cycle

    def corrupted(inp):
        want = original(inp)
        want["io_cancel"] ^= 1
        return want

    env._model.cycle = corrupted
    with pytest.raises(AssertionError, match="io_cancel"):
        env.cycle(CycleInput.idle(), "corrupted reference")
