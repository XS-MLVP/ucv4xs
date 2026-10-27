"""SC full-dirty write-buffer victim: is the all-four-dirty state reachable?

``results/sc-module-qualification-20261020-v2`` left this open with the exact
question: "whether four pending writes can coexist under the public protocol was
not established".  Answering it does not require reading ``rtl/sc``: the
integrated BPU exposes every SC write buffer's four ``shadowValid``/``dirty``
slots and the buffer's drain ready (``io_read_0_ready``) through the already
authorised memory-direct monitor.

This case is a read-only reachability measurement over the physical SC-used
matrix (2 banks x 4 ways).  On every compared cycle it records the dirty
population of all twenty buffers and whether a drain was ever refused:

* if any buffer reaches four dirty slots, the cell is reachable and the
  ``full_overwrite`` contract must be exercised;
* otherwise the report states the observed maximum and the drain-readiness
  history, so the "defensive path" claim rests on bounded evidence rather than
  an assumption.
"""

from __future__ import annotations

import json

import pytest

from bpuverify.bpu.case.sc.used import check_used
from bpuverify.bpu.checker.sc.full import FullScChecker
from bpuverify.common.env.artifacts import write_output


class DirtyWitness(FullScChecker):
    """Record dirty occupancy and drain readiness for every SC write buffer."""

    def __init__(self, case):
        super().__init__(case, capacity=4096)
        self.dirty_max = {}
        self.valid_max = {}
        self.full_cycles = []
        self.ready_low = {}
        self.cycles = 0
        self.saw_reset = False
        self.pre_reset_ignored = 0

    def observe_controls(self, observation):
        super().observe_controls(observation)
        row = observation.value
        if any(frame['reset'] for frame in row['buffers'].values()):
            self.saw_reset = True
            # The reset cycle samples the pre-edge power-on registers, which are
            # not a semantic shadow state (dirty=4 with valid=2 was observed).
            self.pre_reset_ignored += 1
            return
        if not self.saw_reset:
            self.pre_reset_ignored += 1
            return
        self.cycles += 1
        for name, frame in row['buffers'].items():
            dirty = sum(int(slot['dirty']) for slot in frame['slots'])
            valid = sum(int(slot['valid']) for slot in frame['slots'])
            self.dirty_max[name] = max(self.dirty_max.get(name, 0), dirty)
            self.valid_max[name] = max(self.valid_max.get(name, 0), valid)
            if dirty == 4:
                self.full_cycles.append(dict(tick=observation.event.tick, buffer=name,
                    valid=valid, ready=int(frame['drain']['ready'])))
            if not frame['drain']['ready']:
                self.ready_low[name] = self.ready_low.get(name, 0) + 1


@pytest.mark.feature('BPU-SC-019')
@pytest.mark.parametrize('bank', (0, 1), ids=('bank0', 'bank1'))
@pytest.mark.parametrize('way', range(4), ids=lambda value: f'way{value}')
async def test_all_four_dirty_reachability_under_the_public_protocol(
        bpu_agent, bpu_sc_output, request, bank, way):
    """One physical permutation; a fresh agent per run keeps reset state clean."""

    box = {}

    def factory(case):
        box['witness'] = DirtyWitness(case)
        return box['witness']

    await check_used(bpu_agent, bpu_sc_output, 'agree', bank=bank, way=way,
                     checker_factory=factory)
    witness = box['witness']
    report = dict(bank=bank, way=way, cycles=witness.cycles,
                  pre_reset_ignored=witness.pre_reset_ignored,
                  dirty_max=dict(witness.dirty_max), valid_max=dict(witness.valid_max),
                  full_cycles=witness.full_cycles,
                  ready_low=dict(witness.ready_low))
    # Write inside the run's own output directory: an isolated regression
    # reclaims its worker sandbox, so a process-global path would lose the
    # measurement even though the case passed.
    write_output(bpu_sc_output / f'sc-dirty-bank{bank}-way{way}.json',
                 json.dumps(report, indent=2, sort_keys=True) + '\n')
    # The isolated regression reclaims its worker sandbox, so the durable copy
    # must ride the JUnit user properties, exactly like the other witnesses.
    request.node.user_properties.append(
        ('sc_full_dirty_reachability', json.dumps(report, sort_keys=True)))
    # The measurement must have run and stayed within the physical bound.  The
    # reachability conclusion itself is reported, not asserted: both outcomes are
    # legitimate answers to the open contract question.
    assert report['cycles'] > 0
    assert all(value <= 4 for value in report['dirty_max'].values())
