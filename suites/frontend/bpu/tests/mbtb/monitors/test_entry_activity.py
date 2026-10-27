"""Entry observation is mandatory, unambiguous and safely scoped."""
from types import SimpleNamespace

import pytest

from bpuverify.mbtb.agent.main import MbtbAgent
from bpuverify.mbtb.monitor.entry import ENTRY_FIELDS
from bpuverify.mbtb.monitor.entry import MbtbEntryActivityMonitor
from tests.mbtb.monitors.test_counter_activity import FakeMonitor
from tests.framework.fakes import native_name_dut


def test_entry_monitor_requires_picker_native_observation():
    with pytest.raises(RuntimeError, match="picker --rw mem_direct"):
        MbtbEntryActivityMonitor(SimpleNamespace())


@pytest.mark.parametrize("count", (0, 2))
def test_missing_or_ambiguous_entry_signal_fails_with_signal_location(count, tmp_path):
    suffix = ".MainBtb.alignBanks_0.internalBanks_0.entryWriteBuffer.io_write_0_valid"
    dut = native_name_dut(tmp_path, tuple(f"top{i}{suffix}" for i in range(count)))
    with pytest.raises(RuntimeError, match=rf"io_write_0_valid.*found {count}"):
        MbtbEntryActivityMonitor(dut)


def test_entry_decoder_captures_all_eight_ports_and_freezes_payloads():
    class Word:
        def __init__(self, value):
            self.value = value

        def as_int(self):
            return self.value

    def port(index):
        values = {key: Word(index) for key in ("write_valid", "read_valid", "read_ready")}
        values.update({f"{direction}_{key}": Word(index * 20 + offset)
                       for direction in ("write", "read") for offset, (key, _) in enumerate(ENTRY_FIELDS)})
        return SimpleNamespace(**values)

    sample = SimpleNamespace(banks=tuple(tuple(tuple(port(align * 4 + bank * 2 + way) for way in range(2))
                                               for bank in range(2)) for align in range(2)))
    actual = MbtbEntryActivityMonitor.decode(sample)
    for align in range(2):
        for bank in range(2):
            for way in range(2):
                value = actual["banks"][align][bank][way]
                index = align * 4 + bank * 2 + way
                assert value["write_valid"] == index and value["read_lower"] == index * 20 + 6
    sample.banks[1][1][1].write_carry.value = 100
    assert actual["banks"][1][1][1]["write_carry"] == 145


def owner(native=None, inputs=None):
    return SimpleNamespace(_started=True, _execution=object(), _entry_activity_active=False,
                           _counter_activity_active=False, _entry_monitor=native or FakeMonitor(),
                           _entry_input_monitor=inputs or FakeMonitor(), _counter_monitor=FakeMonitor(),
                           _counter_input_monitor=FakeMonitor())


async def test_entry_scope_requires_started_agent():
    agent = owner()
    agent._started = False
    with pytest.raises(RuntimeError, match="started MainBTB"):
        async with MbtbAgent.observe_entry_activity(agent):
            pass


@pytest.mark.parametrize("inner", ("entry", "counter"))
async def test_entry_scope_rejects_both_observation_nesting_modes(inner):
    agent = owner()
    async with MbtbAgent.observe_entry_activity(agent):
        observe = MbtbAgent.observe_entry_activity if inner == "entry" else MbtbAgent.observe_counter_activity
        with pytest.raises(RuntimeError, match="already active"):
            async with observe(agent):
                pass
    assert not agent._entry_activity_active and not agent._counter_activity_active


async def test_counter_scope_rejects_entry_observation_nesting():
    agent = owner()
    async with MbtbAgent.observe_counter_activity(agent):
        with pytest.raises(RuntimeError, match="already active"):
            async with MbtbAgent.observe_entry_activity(agent):
                pass
    assert not agent._entry_activity_active and not agent._counter_activity_active


@pytest.mark.parametrize("which", ("native", "input"))
async def test_entry_scope_closes_both_monitors_after_start_error(which):
    native, inputs = FakeMonitor(fail_start=which == "native"), FakeMonitor(fail_start=which == "input")
    agent = owner(native, inputs)
    with pytest.raises(RuntimeError, match="start failed"):
        async with MbtbAgent.observe_entry_activity(agent):
            pass
    assert native.closed and inputs.closed and not agent._entry_activity_active


async def test_entry_scope_closes_after_body_error_and_collects_only_valid_inputs():
    agent = owner()
    with pytest.raises(RuntimeError, match="body failed"):
        async with MbtbAgent.observe_entry_activity(agent) as trace:
            valid = SimpleNamespace(value={"valid": 1})
            agent._entry_input_monitor.observer(SimpleNamespace(value={"valid": 0}))
            agent._entry_input_monitor.observer(valid)
            agent._entry_monitor.observer(valid)
            assert trace.feedback == trace.frames == [valid]
            raise RuntimeError("body failed")
    assert agent._entry_monitor.closed and agent._entry_input_monitor.closed and not agent._entry_activity_active


@pytest.mark.parametrize("which", ("native", "input"))
async def test_entry_scope_restores_flag_even_if_close_fails(which):
    agent = owner(native=FakeMonitor(fail_close=which == "native"), inputs=FakeMonitor(fail_close=which == "input"))
    with pytest.raises(RuntimeError, match="close failed"):
        async with MbtbAgent.observe_entry_activity(agent):
            pass
    assert agent._entry_monitor.closed and agent._entry_input_monitor.closed and not agent._entry_activity_active


@pytest.mark.parametrize("active,mode,error", ((False, "blocked", RuntimeError), (True, "queue", ValueError)))
async def test_checked_entry_overlap_rejects_invalid_scope_before_drive(active, mode, error):
    with pytest.raises(error):
        await MbtbAgent.train_entry_during_predictions_checked(SimpleNamespace(_entry_activity_active=active),
            (object(),), (object(),), None, expected_activity={}, mode=mode)
