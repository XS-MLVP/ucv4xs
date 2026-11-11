"""Full configured shapes/physical aliases; synthetic controls, no DUT credit."""
from types import SimpleNamespace as NS

import pytest
from toffee import Bundle

from suites.frontend.bpu.testbenches.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.testbenches.bpu.checker.sc.role_scenarios import ZeroHistoryChecker
from suites.frontend.bpu.testbenches.bpu.model.phr.model import LENGTH
from suites.frontend.bpu.testbenches.bpu.model.phr.model import LAYOUT
from suites.frontend.bpu.testbenches.bpu.model.bypass.sram import pack_data
from suites.frontend.bpu.testbenches.bpu.checker.abtb.write import WriteChecker
from suites.frontend.bpu.testbenches.bpu.env.monitor.bypass import sram_base
from suites.frontend.bpu.testbenches.bpu.env.monitor.bypass import hash as hash_monitor
from suites.frontend.bpu.testbenches.utage.model.semantic import INDEX_FOLDS
from suites.frontend.bpu.testbenches.utage.model.semantic import S1_HISTORY_INDICES
from suites.frontend.bpu.testbenches.shared.env.bundle.bindings import PortBinding
from suites.frontend.bpu.testbenches.shared.tests.framework.fakes import Signal, event

pytestmark = pytest.mark.selftest


def zero_row():
    return dict(state=dict(cells=[0] * LENGTH,
        **{bank: [0] * len(LAYOUT) for bank in ('fold0_reg', 'fold1', 'fold2', 'fold3')}),
        boundary=dict(redirect=dict(valid=0),
            **{stage: dict(valid=0) for stage in ('s1', 's2', 's3')}))


@pytest.mark.parametrize('fault', (None, 'legacy-cells', 'legacy-folds', 'last-cell',
    'last-fold0_reg', 'last-fold1', 'last-fold2', 'last-fold3'))
def test_zero_history_premise_checks_every_configured_cell_and_fold(monkeypatch, fault):
    # Isolate the additional all-zero premise from the already-tested complete
    # PHR/UID checker. Only this unit's base observe is replaced, never production.
    monkeypatch.setattr(BpuPhrChecker, 'observe', lambda self, obs:
                        self.records.append(dict(tick=obs.event.tick)))
    checker = ZeroHistoryChecker(scope='configured-zero-history-control')
    checker.records.append(dict(tick=0))
    sample = zero_row()
    if fault == 'legacy-cells':
        sample['state']['cells'] = [0] * 52
    elif fault == 'legacy-folds':
        sample['state']['fold1'] = [0] * 19
    elif fault == 'last-cell':
        sample['state']['cells'][-1] = 1
    elif fault is not None:
        sample['state'][fault.removeprefix('last-')][-1] = 1
    checker.capture(NS(value=sample, event=event(2)))
    if fault:
        with pytest.raises(AssertionError) as first:
            checker.raise_failure()
        with pytest.raises(AssertionError) as last:
            checker.raise_failure()
        assert first.value is last.value
    else:
        checker.raise_failure()
        assert checker.scoreboard.status.checked == checker.scoreboard.status.passed == 6
    assert LENGTH == 532 and len(LAYOUT) == 33


def test_zero_path_hash_uses_current_half_block_not_legacy_eight_halfwords(monkeypatch):
    monkeypatch.setattr(BpuPhrChecker, 'observe', lambda self, obs:
                        self.records.append(dict(tick=obs.event.tick)))
    checker = ZeroHistoryChecker(scope='current-half-block')
    checker.records.append(dict(tick=0))
    sample = zero_row()
    sample['boundary']['s1'] = dict(valid=1, start_pc=0x40000008,
        prediction=dict(taken=1, position=2, target=0x40))
    checker.capture(NS(value=sample, event=event(2)))
    checker.raise_failure()
    assert checker.scoreboard.status.checked == 7


@pytest.mark.parametrize('field,width,shift', (
    ('counter', 3, 1), ('position', 5, 4), ('tag', 8, 9), ('data_valid', 1, 17)))
def test_current_serialization_retains_each_bit_without_overlap(field, width, shift):
    for bit in range(width):
        payload = dict(data_valid=0, tag=0, position=0, counter=0)
        payload[field] = 1 << bit
        assert pack_data(payload) == 1 << (bit + shift)


@pytest.mark.parametrize('missing_enable', (None, 'rckEn', 'finalRamWen'))
def test_sram_observer_binds_physical_enables_or_fails_without_defaults(monkeypatch, missing_enable):
    def base_init(self, agent):
        self.prefixes = ['Bpu.utage.MicroTageTable.wbuffer.']
        self.binding = PortBinding(agent.dut.clock,
            Bundle(reset=Signal(), tables=Bundle(marker=Signal())), 'test.synthetic-shadow')

    seen = []

    def signal(dut, name):
        seen.append(name)
        if missing_enable and name.endswith('.' + missing_enable):
            raise RuntimeError('missing physical enable ' + name)
        return Signal()

    monkeypatch.setattr(sram_base.BypassMonitor, '__init__', base_init)
    monkeypatch.setattr(sram_base, 'memory_signal', signal)
    agent = NS(dut=NS(clock=Signal()))
    if missing_enable:
        with pytest.raises(RuntimeError, match='missing physical enable'):
            sram_base.SramMonitor(agent)
    else:
        monitor = sram_base.SramMonitor(agent)
        assert len(monitor.binding.bits.sram[0].banks) == 4
        for bank in range(4):
            prefix = f'Bpu.utage.MicroTageTable.utage_entry_sram_bank{bank}.'
            assert prefix + 'rckEn' in seen and prefix + 'finalRamWen' in seen
            assert prefix + 'ren' not in seen and prefix + 'wen' not in seen


def test_hash_observer_uses_the_current_sparse_fold_indices_without_silent_defaults(monkeypatch):
    def base_init(self, agent):
        self.prefixes = ['Bpu.utage.MicroTageTable.wbuffer.']
        self.binding = PortBinding(agent.dut.clock, Bundle(marker=Signal()), 'test.synthetic-sram')

    seen = []
    def signal(dut, name):
        seen.append(name)
        if 'io_normalPathHist_hist_9_' in name or 'io_s1PathHist_hist_8_' in name:
            raise AssertionError('legacy folded-history index')
        return Signal()

    monkeypatch.setattr(hash_monitor._v14.SramMonitor, '__init__', base_init)
    monkeypatch.setattr(hash_monitor, 'memory_signal', signal)
    monitor = hash_monitor.SramMonitor(NS(dut=NS(clock=Signal())))
    assert INDEX_FOLDS == (2, 7) and S1_HISTORY_INDICES == (1, 2, 5, 6)
    assert len(monitor.binding.bits.hash_inputs.normal_folds) == 2
    assert len(monitor.binding.bits.hash_inputs.s1_folds) == 4
    assert {f'Bpu.utage.io_normalPathHist_hist_{index}_foldedHist' for index in INDEX_FOLDS} <= set(seen)
    assert {f'Bpu.utage.io_s1PathHist_hist_{index}_foldedHist' for index in S1_HISTORY_INDICES} <= set(seen)


@pytest.mark.parametrize('sibling_fails', (False, True))
def test_direct_checker_preserves_sibling_first_error_without_accepting_stale_frames(monkeypatch, sibling_fails):
    root = AssertionError('real prior sibling mismatch')
    def raise_failure():
        if sibling_fails:
            raise root

    parent = NS(failure=None, bypass=NS(raise_failure=raise_failure))
    checker = WriteChecker(parent)
    visited = []
    def observe(self, phase, observation):
        visited.append(observation.event.tick)
        self.check(1045, 1044, field='same_event_as_history_hash_capture')

    monkeypatch.setattr(WriteChecker, 'observe', observe)
    checker.capture('preedge', NS(event=event(1045), value={}))
    if sibling_fails:
        assert visited == [] and checker.failure is parent.failure is root
    else:
        assert visited == [1045] and checker.failure is parent.failure
        assert checker.failure is not root
        assert 'expected 1045' in str(checker.failure)
    # Neither the first sibling mismatch nor a real unsynchronized observation
    # can be paid by a later invocation after failure.
    checker.capture('rising', NS(event=event(1046), value={}))
    assert len(visited) == int(not sibling_fails)
