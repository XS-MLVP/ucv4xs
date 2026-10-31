"""Synthetic only: binding mechanics and every directly compared field.

No generated snapshot below is claimed to be a real hardware observation.
"""
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
import yaml
from toffee import ClockCycles
from toffee import Execution
from toffee import MemoryBackend
from toffee import ScoreboardMismatch
from toffee import Transfer
from suites.frontend.bpu.bpu.bundle.values import _plain
from suites.frontend.bpu.bpu.checker.abtb.write import WriteChecker as DirectChecks
from suites.frontend.bpu.bpu.checker.abtb.write import entry
from suites.frontend.bpu.bpu.checker.abtb.write import expected_ports
from suites.frontend.bpu.bpu.checker.abtb.write import qualified
from suites.frontend.bpu.bpu.checker.abtb.write import read_inputs
from suites.frontend.bpu.bpu.monitor.abtb.write import ENTRY_NAMES
from suites.frontend.bpu.bpu.monitor.abtb.write import WriteMonitor
from suites.frontend.bpu.bpu.env.abtb.write import WriteObservation as DirectObservation
from suites.frontend.bpu.bpu.model.abtb.write import WriteLineageReference

STAGE = Path(__file__).resolve().parent
RTL = Path(__file__).resolve().parents[4] / 'rtl/bpu'


class ReadOnlySignal:
    def __init__(self, value=0):
        self.value = value

    def U(self):
        return self.value

    def W(self):
        return 64

    def IsVPIBinded(self):
        return False

    def Set(self, value):
        raise AssertionError('passive monitor attempted a signal write')


@lru_cache(maxsize=1)
def declared_abtb_suffixes():
    # Real trace declarations supply names only. Synthetic tests never read
    # a native address or construct a hardware DUT.
    layout = RTL.parents[1] / 'dut/bpu/BpuDut_offset.yaml'
    metadata = yaml.load(layout.read_bytes(), Loader=yaml.CSafeLoader)
    prefix = 'BpuDut_top.Bpu.abtb.'
    names = tuple(row['name'].removeprefix(prefix)
        for row in metadata['signals'] if row['name'].startswith(prefix))
    assert 'takenCounter_0_0_0_value' in names and 'reset' in names
    return names


class FakeDut:
    layout = None

    def __init__(self, *, missing=None, hierarchies=1):
        self.clock, self.reset, self.signals = object(), ReadOnlySignal(1), {}
        names = tuple(f'bpu{number}.abtb.' + suffix
            for number in range(hierarchies) for suffix in declared_abtb_suffixes()
            if f'bpu{number}.abtb.' + suffix != missing)
        names = names or ('unrelated.clock',)
        assert self.layout is not None

        def bind(path, label):
            assert path in names and label == 'MEM_DIRECT:' + path
            return self.signals.setdefault(path,
                ReadOnlySignal(self.reset.value if path.endswith('.reset') else 0))

        self.dut = SimpleNamespace(GetXSignalCFGBasePtr=lambda: 1,
            GetXSignalCFGPath=lambda: str(self.layout))
        self.xcfg = SimpleNamespace(cfg_base_address=1, cfg_data=str(self.layout),
            GetSignalNames=lambda: names, NewXData=bind,
            At=lambda path: SimpleNamespace(is_empty=False,
                rtl_width=64, mem_bytes=8, array_size=0))

    def GetInternalSignalList(self, **kwargs):
        raise AssertionError('VPI/internal discovery is forbidden')

    def GetInternalSignal(self, *args, **kwargs):
        raise AssertionError('VPI/internal reads are forbidden')


@pytest.fixture(autouse=True)
def synthetic_native_layout(tmp_path, monkeypatch):
    layout = tmp_path / 'synthetic-offset.yaml'
    layout.write_text('variables: []\n', encoding='utf-8')
    monkeypatch.setattr(FakeDut, 'layout', layout)


def agent(**changes):
    return SimpleNamespace(dut=FakeDut(**changes), _execution=None)


def tx(bank=0, entry_set=1):
    return dict(pc=0x40010001, target=0x40010101, taken=1, position=7, branch_type=1, ras_action=0,
        meta=dict(valid=1, bankMask=1 << bank, setIdx=entry_set, entries=[dict(hit=0, position=0,
            attribute=dict(branchType=0, rasAction=0), targetLowerBits=0) for _ in range(4)]))


def ready():
    reference = WriteLineageReference()
    reference.advance(reset=1, accepted=None, read_pressure=[0] * 4)
    for _ in range(64):
        reference.advance(reset=0, accepted=None, read_pressure=[0] * 4)
    return reference


def fixture(bank=0):
    reference = ready()
    reference.advance(reset=0, accepted=tx(bank), read_pressure=[1] * 4)
    reference.advance(reset=0, accepted=None, read_pressure=[1] * 4)
    reference.advance(reset=0, accepted=tx(bank, 2), read_pressure=[1] * 4)
    reference.advance(reset=0, accepted=None, read_pressure=[1] * 4)
    # Old dirty slot plus a fresh registered T2 request, both fully qualified.
    assert reference.buffers[bank].slots[0]['dirty'] and reference.request2[bank] is not None
    reads = [[entry(payload) for payload in reference.sram[number][1]] for number in range(4)]
    wanted = expected_ports(reference, [0] * 4, 1, reads)
    return reference, wanted


def compare(wanted, actual):
    checker = DirectChecks(SimpleNamespace(failure=None))
    checker.event = SimpleNamespace(tick=100)
    checker.check(wanted, qualified(actual, wanted), field='synthetic_all_full_shadow_T2_and_SRAM_ports')
    return checker


def test_binding_is_static_readonly_and_every_leaf_exists_in_matching_compiled_RTL_text():
    monitor = WriteMonitor(agent())
    assert len(monitor.signal_paths) == len(set(monitor.signal_paths))
    assert len(monitor.signal_paths) > 500
    for path in monitor.signal_paths:
        suffix = path.removeprefix('bpu0.abtb.')
        parts = suffix.split('.')
        name = 'WriteBuffer.sv' if len(parts) == 3 and parts[1] == 'writeBuffer' else\
            'SplittedSRAMTemplate_2.sv' if len(parts) == 3 and parts[1] == 'sram' else 'AheadBtbBank.sv'
        assert re.search(r'\b' + re.escape(parts[-1]) + r'\b', (RTL / name).read_text()), (path, name)
    snapshot = _plain(monitor.binding.bits.sample())
    assert snapshot['reset'] == 1 and len(snapshot['banks']) == 4
    assert len(snapshot['banks'][0]['slots']) == 4
    assert set(snapshot['banks'][0]['slots'][0]['payload']) == set(ENTRY_NAMES) | {'need_reset', 'set_index', 'way'}


@pytest.mark.parametrize('count', (0, 2))
def test_ambiguous_or_missing_ABTB_hierarchy_fails_binding_instead_of_choosing_any_bank(count):
    with pytest.raises(RuntimeError, match='unique integrated ABTB'):
        WriteMonitor(agent(hierarchies=count))


@pytest.mark.parametrize('path', (
    'bpu0.abtb.banks_3.writeBuffer.entries_0_2_entry_targetLowerBits', 'bpu0.abtb.reset'))
def test_missing_full_payload_leaf_reports_exact_path_before_subscription(path):
    with pytest.raises(RuntimeError, match=re.escape(path)):
        WriteMonitor(agent(missing=path))


async def test_two_phase_on_capture_is_snapshot_based_and_closes_all_subscriptions():
    owner = agent()
    monitor, captures = WriteMonitor(owner), []
    checker = SimpleNamespace(capture=lambda phase, sample: captures.append((phase, sample)))
    async with Execution(MemoryBackend(owner.dut.clock)) as execution:
        owner._execution = execution
        monitor.start(checker)
        with pytest.raises(RuntimeError, match='already started'):
            monitor.start(checker)
        await ClockCycles(owner.dut.clock, 1)
        assert {phase for phase, _ in captures} == {'rising', 'preedge'}
        first = list(captures)
        path = 'bpu0.abtb.banks_0.writeBuffer.entries_0_0_entry_tag'
        owner.dut.signals[path].value = 123
        await ClockCycles(owner.dut.clock, 1)
        assert all(sample.value['banks'][0]['slots'][0]['payload']['tag'] == 0 for _, sample in first)
        assert any(sample.value['banks'][0]['slots'][0]['payload']['tag'] == 123 for _, sample in captures)
        await monitor.aclose()
        count = len(captures)
        await ClockCycles(owner.dut.clock, 1)
        assert len(captures) == count and monitor.subscriptions == []


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('slot', range(4))
@pytest.mark.parametrize('field', ('shadow_valid', 'dirty', 'need_reset', 'set_index', 'way',
    'valid', 'tag', 'position', 'branch_type', 'ras_action', 'target_low'))
def test_each_of_all16_shadow_slots_and_full_payload_fields_rejects_a_single_wrong_bit(bank, slot, field):
    _, wanted = fixture(bank)
    actual = deepcopy(wanted)
    node = actual[bank]['slots'][slot]
    if field not in ('shadow_valid', 'dirty'):
        node = node['payload']
    node[field] ^= 1
    with pytest.raises(ScoreboardMismatch) as caught:
        compare(wanted, actual)
    error = caught.value
    assert error.differences and error.status.failed == 1
    assert error.context.observed_event.tick == 100
    assert field in str(error)


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('port', ('request', 'write', 'drain'))
@pytest.mark.parametrize('field', ('need_reset', 'set_index', 'way', 'valid', 'tag',
    'position', 'branch_type', 'ras_action', 'target_low'))
def test_complete_outer_T2_inner_write_and_dirty_drain_payloads_are_all_compared(bank, port, field):
    _, wanted = fixture(bank)
    actual = deepcopy(wanted)
    actual[bank][port]['bits'][field] ^= 1
    with pytest.raises(ScoreboardMismatch):
        compare(wanted, actual)


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('way', range(4))
@pytest.mark.parametrize('field', tuple(ENTRY_NAMES))
def test_every_SRAM_write_lane_and_read_lane_field_is_compared(bank, way, field):
    _, wanted = fixture(bank)
    for kind in ('write', 'read'):
        actual = deepcopy(wanted)
        lane = actual[bank]['sram']['write']['entries'][way] if kind == 'write' else actual[bank]['sram']['read'][way]
        lane[field] ^= 1
        with pytest.raises(ScoreboardMismatch):
            compare(wanted, actual)


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('path', (('plru',), ('reset_done',), ('request', 'valid'), ('write', 'valid'),
    ('drain', 'valid'), ('drain', 'ready'), ('read_input', 'valid'), ('sram', 'ready'),
    ('sram', 'write', 'valid'), ('sram', 'write', 'set_index'), ('sram', 'write', 'way_mask')))
def test_all_control_and_arbitration_fields_reject_wrong_values(bank, path):
    _, wanted = fixture(bank)
    actual = deepcopy(wanted)
    node = actual[bank]
    for name in path[:-1]:
        node = node[name]
    node[path[-1]] ^= 1
    with pytest.raises(ScoreboardMismatch):
        compare(wanted, actual)


def test_invalid_payloads_are_unqualified_but_missing_required_fields_or_slots_fail():
    reference = ready()
    wanted = expected_ports(reference, [0] * 4, 0, [None] * 4)
    actual = deepcopy(wanted)
    actual[0]['request']['bits'] = {'arbitrary_inactive_bits': 123}
    actual[0]['sram']['read'] = ['never_read_unknown_output']
    assert compare(wanted, actual).scoreboard.status.failed == 0
    for fault in ('missing_key', 'missing_slot'):
        actual = deepcopy(wanted)
        if fault == 'missing_key':
            del actual[0]['slots'][0]['payload']['target_low']
        else:
            actual[0]['slots'].pop()
        with pytest.raises(ScoreboardMismatch):
            compare(wanted, actual)


@pytest.mark.parametrize('bank', range(4))
def test_read_pressure_and_read_index_are_derived_from_halfword_PC_fold_and_fire(bank):
    values = dict(hash_inputs=dict(pc=0x40010008, normal_folds=[bank]),
        index_boundary=dict(enable=1, fire0=1))
    pressure, index = read_inputs(values)
    assert pressure == [int(number == bank) for number in range(4)] and index == 4
    values['index_boundary']['fire0'] = 0
    assert read_inputs(values)[0] == [0] * 4


def test_capture_failure_is_latched_on_owner_and_rethrown_with_state_and_exact_event():
    owner = SimpleNamespace(failure=None)
    checker = DirectChecks(owner)
    observation = Transfer(event=SimpleNamespace(tick=7), value=dict(reset=0, banks=[]))
    checker.capture('wrong-phase', observation)
    assert isinstance(owner.failure, ScoreboardMismatch) and checker.failure is owner.failure
    assert checker.failed_frame['tick'] == 7
    with pytest.raises(ScoreboardMismatch) as caught:
        checker.summary()
    assert caught.value.status.failed == 1 and caught.value.context.observed_event.tick == 7


async def test_scope_cleanup_preserves_resume_streams_and_closes_children_even_after_failure(monkeypatch):
    from suites.frontend.bpu.bpu.env.phr.observation import BpuPhrObservation
    order = []
    async def base_close(self, *, resume_streams):
        order.append(('base', resume_streams))
    class Child:
        def __init__(self, name, fail=False):
            self.name, self.fail = name, fail
        async def aclose(self):
            order.append(self.name)
            if self.fail:
                raise RuntimeError(self.name)
    monkeypatch.setattr(BpuPhrObservation, 'aclose', base_close)
    scope = DirectObservation(SimpleNamespace(), SimpleNamespace(failure=None))
    scope.write_monitor, scope.bypass_monitor = Child('write', True), Child('bypass')
    with pytest.raises(RuntimeError, match='write'):
        await scope.aclose(resume_streams=False)
    assert order == ['write', 'bypass', ('base', False)]


@pytest.mark.parametrize('requested_reset', (0, 1))
def test_full_two_phase_checker_advances_only_preedge_and_holds_reset_derived_SRAM_read_data(requested_reset):
    owner = SimpleNamespace(failure=None, accepts=[], control_records=[],
        bypass=SimpleNamespace(records=[]), current_rise=None)
    checker = DirectChecks(owner)
    tick = 0

    def cycle(*, reset=0, accepted=None, read=False, requested_reset=None):
        nonlocal tick
        values = dict(reset=reset, hash_inputs=dict(pc=2, normal_folds=[0], s2_override=0,
            s3_override=0, redirect_valid=0), index_boundary=dict(enable=1, fire0=int(read)))
        for phase in ('rising', 'preedge'):
            tick += 1
            ref, idx = checker.reference, checker.index
            pressure, read_index = read_inputs(values)
            current = deepcopy(accepted) if phase == 'preedge' else None
            if current is not None:
                owner.accepts.append(dict(tick=tick, transaction=current))
            meta = dict(valid=int(idx.initialized and idx.s2_valid),
                setIdx=0 if idx.s2 is None else idx.s2['entry_set'],
                bankMask=0 if idx.s2 is None else 1 << idx.s2['bank'],
                entries=tx()['meta']['entries'])
            row = dict(reset=reset if requested_reset is None else requested_reset, abtb=dict(enable=1, meta1=meta,
                cells=ref.counter.cells[:], replacers=[dict(states=state[:]) for state in ref.counter.plru],
                fast=dict(valid=int(current is not None), meta=dict(valid=int(current is not None))),
                capture=dict(fire1=1, fire2=1), writes=[dict(valid=0) for _ in range(4)]))
            if ref.initialized and not reset:
                for bank, buffer in enumerate(ref.buffers):
                    dirty = next((slot['payload'] for slot in buffer.slots if slot['dirty']), None)
                    if dirty is not None and not pressure[bank] and ref.reset_remaining == 0:
                        row['abtb']['writes'][bank] = dict(valid=1, set_index=dirty['set_index'],
                            way=dirty['way'], reset_counter=dirty['need_reset'])
            observation = Transfer(event=SimpleNamespace(tick=tick), value=dict(reset=reset,
                banks=[] if not ref.initialized else expected_ports(ref, pressure, read_index, checker.read_data)))
            if phase == 'rising':
                owner.current_rise = Transfer(event=observation.event, value=row)
            else:
                row['tick'] = tick
                owner.control_records.append(row)
            owner.bypass.records.append(dict(tick=tick, phase=phase, value=values))
            checker.observe(phase, observation)

    cycle(reset=1, requested_reset=requested_reset)
    assert checker.reference.reset_remaining == 64
    for _ in range(64):
        cycle(requested_reset=requested_reset)
    assert checker.reference.reset_remaining == 0
    assert checker.read_data == [None] * 4
    cycle(accepted=tx(0, 1))
    for _ in range(4):
        cycle()
    assert checker.reference.sram[0][1][0]['valid'] == 1
    cycle(read=True)
    assert checker.read_data[0][0]['tag'] == tx()['pc'] & ((1 << 24) - 1)
    assert checker.read_data[0][0]['target_low'] == tx()['target'] & ((1 << 22) - 1)
    held = deepcopy(checker.read_data)
    cycle()
    cycle()
    assert checker.read_data == held
    assert checker.summary()['confirmed_actions'] == 1
    cycle(reset=1)
    assert checker.read_data == [None] * 4 and checker.reference.reset_remaining == 64


def test_prior_sibling_checker_failure_is_not_replaced_or_reported_as_success():
    original = RuntimeError('first independent bypass failure')
    def parent_check():
        raise original
    owner = SimpleNamespace(failure=None, bypass=SimpleNamespace(failure=original), raise_failure=parent_check)
    checker = DirectChecks(owner)
    observation = Transfer(event=SimpleNamespace(tick=9), value=dict(reset=0, banks=[]))
    checker.capture('wrong-phase', observation)
    assert owner.failure is None and checker.failure is None and checker.records == []
    with pytest.raises(RuntimeError) as caught:
        checker.summary()
    assert caught.value is original


def test_pending_public_reset_cache_cannot_replace_committed_internal_reset():
    owner = agent()
    monitor = WriteMonitor(owner)
    committed = owner.dut.signals['bpu0.abtb.reset']
    assert monitor.binding.bits.reset is committed
    owner.dut.reset.value = 0
    assert _plain(monitor.binding.bits.sample())['reset'] == 1
    committed.value = 0
    owner.dut.reset.value = 1
    assert _plain(monitor.binding.bits.sample())['reset'] == 0


def test_native_binding_cache_is_per_model_and_closed_handle_lookup_fails():
    from suites.frontend.bpu.runtime.memory_direct import memory_signal
    from suites.frontend.bpu.runtime.memory_direct import require_memory_direct
    first, second = agent(), agent()
    one, two = WriteMonitor(first), WriteMonitor(second)
    assert one.binding.bits.reset is not two.binding.bits.reset
    assert one.binding.bits.reset is memory_signal(first.dut, 'bpu0.abtb.reset')
    require_memory_direct(first.dut).close()
    with pytest.raises(RuntimeError, match='closed DUT'):
        memory_signal(first.dut, 'bpu0.abtb.reset')
    assert memory_signal(second.dut, 'bpu0.abtb.reset') is two.binding.bits.reset


def test_native_capability_failure_cannot_fall_back_to_legacy_internal_getters():
    owner = agent()
    owner.dut.dut.GetXSignalCFGBasePtr = lambda: 0
    with pytest.raises(RuntimeError, match='base is zero'):
        WriteMonitor(owner)
