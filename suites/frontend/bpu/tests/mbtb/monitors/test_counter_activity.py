"""Counter native bindings are explicit requirements, not silent skips."""
from types import SimpleNamespace

import pytest

from bpuverify.mbtb.agent.main import MbtbAgent
from bpuverify.mbtb.monitor.counter import MbtbCounterActivityMonitor
from bpuverify.mbtb.monitor.counter import QUEUE_FIELDS
from tests.framework.fakes import native_name_dut


def test_counter_monitor_requires_picker_native_observation():
    with pytest.raises(RuntimeError, match="picker --rw mem_direct"):
        MbtbCounterActivityMonitor(SimpleNamespace())


@pytest.mark.parametrize("count", (0, 2))
def test_missing_or_ambiguous_counter_signal_fails_with_signal_location(count, tmp_path):
    suffix = ".MainBtb.alignBanks_0.internalBanks_0.counterWriteBuffer.io_enq_valid"
    dut = native_name_dut(tmp_path, tuple(f"top{i}{suffix}" for i in range(count)))
    with pytest.raises(RuntimeError, match=rf"io_enq_valid.*found {count}"):
        MbtbCounterActivityMonitor(dut)


def test_counter_decoder_captures_all_four_queues_without_aliasing():
    class Word:
        def __init__(self, value):
            self.value = value

        def as_int(self):
            return self.value

    def queue(index):
        fields = {key: Word(index * 20 + offset) for offset, (key, _) in enumerate(QUEUE_FIELDS)}
        fields.update(enq_counters=(Word(index), Word(index + 1)),
                      deq_counters=(Word(index + 2), Word(index + 3)))
        return SimpleNamespace(**fields)

    sample = SimpleNamespace(queues=((queue(0), queue(1)), (queue(2), queue(3))))
    actual = MbtbCounterActivityMonitor.decode(sample)
    assert actual["queues"][1][1]["enq_counters"] == (3, 4)
    assert actual["queues"][0][1]["deq_counters"] == (3, 4)
    sample.queues[1][1].enq_valid.value = 100
    assert actual["queues"][1][1]["enq_valid"] == 60


class FakeMonitor:
    def __init__(self, *, fail_start=False, fail_close=False):
        self.fail_start, self.fail_close = fail_start, fail_close
        self.closed = False

    def start(self, execution, *, observer):
        self.observer = observer
        if self.fail_start:
            raise RuntimeError("start failed")

    async def aclose(self):
        self.closed = True
        if self.fail_close:
            raise RuntimeError("close failed")


def owner(native=None, inputs=None):
    return SimpleNamespace(_started=True, _execution=object(), _counter_activity_active=False,
                           _counter_monitor=native or FakeMonitor(),
                           _counter_input_monitor=inputs or FakeMonitor())


async def test_counter_scope_requires_started_agent():
    agent = owner()
    agent._started = False
    with pytest.raises(RuntimeError, match="started MainBTB"):
        async with MbtbAgent.observe_counter_activity(agent):
            pass


async def test_counter_scope_rejects_nesting():
    agent = owner()
    async with MbtbAgent.observe_counter_activity(agent):
        with pytest.raises(RuntimeError, match="already active"):
            async with MbtbAgent.observe_counter_activity(agent):
                pass
    assert not agent._counter_activity_active


@pytest.mark.parametrize("which", ("native", "input"))
async def test_counter_scope_closes_both_monitors_after_start_error(which):
    native, inputs = FakeMonitor(fail_start=which == "native"), FakeMonitor(fail_start=which == "input")
    agent = owner(native, inputs)
    with pytest.raises(RuntimeError, match="start failed"):
        async with MbtbAgent.observe_counter_activity(agent):
            pass
    assert native.closed and inputs.closed and not agent._counter_activity_active


async def test_counter_scope_closes_after_body_error_and_collects_only_valid_inputs():
    agent = owner()
    with pytest.raises(RuntimeError, match="body failed"):
        async with MbtbAgent.observe_counter_activity(agent) as trace:
            valid = SimpleNamespace(value={"valid": 1})
            agent._counter_input_monitor.observer(SimpleNamespace(value={"valid": 0}))
            agent._counter_input_monitor.observer(valid)
            agent._counter_monitor.observer(valid)
            assert trace.feedback == trace.frames == [valid]
            raise RuntimeError("body failed")
    assert agent._counter_monitor.closed and agent._counter_input_monitor.closed
    assert not agent._counter_activity_active


async def test_counter_scope_restores_flag_even_if_input_close_fails():
    agent = owner(inputs=FakeMonitor(fail_close=True))
    with pytest.raises(RuntimeError, match="close failed"):
        async with MbtbAgent.observe_counter_activity(agent):
            pass
    assert agent._counter_monitor.closed and not agent._counter_activity_active
