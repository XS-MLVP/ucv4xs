"""Fail fast at unsupported inputs/capabilities and every missing cross bin."""
from itertools import product
from types import SimpleNamespace

import pytest
from bpuverify.ras.agent.main import RasAgent
from bpuverify.ras.transaction.types import RasOperation
from bpuverify.ras.driver.encoding import encode_cfi_pc
from bpuverify.ras.monitor.observation import RasCommittedMonitor
from bpuverify.ras.coverage.supplemental import ras_committed_cells_coverage_model as committed_coverage
from bpuverify.ras.coverage.supplemental import ras_adjacent_coverage_model as adjacent_coverage
from bpuverify.ras.coverage.supplemental import ras_redirect_redo_coverage_model as redirect_coverage
from bpuverify.ras.case.adjacent_cases import cases
from tests.framework.fakes import native_name_dut


@pytest.mark.parametrize('kwargs', (
    dict(action=-1), dict(action=4), dict(action=True), dict(action=None),
    dict(action=2, start_pc=-1), dict(action=2, start_pc=1 << 51), dict(action=2, start_pc=True),
    dict(action=2, position=-1), dict(action=2, position=16), dict(action=2, position=True),
    dict(action=2, enable=-1), dict(action=2, enable=2), dict(action=2, enable=True),
    dict(action=2, branch_type=-1), dict(action=2, branch_type=4), dict(action=2, branch_type=True),
))
def test_invalid_operation_is_rejected_before_any_drive(kwargs):
    with pytest.raises(ValueError, match='RAS'):
        RasOperation(**kwargs)


@pytest.mark.parametrize('action,branch_type', ((0, 2), (1, 3), (2, 2), (3, 3)))
def test_action_default_and_explicit_branch_type(action, branch_type):
    assert RasOperation(action).frame()['branch_type'] == branch_type
    assert RasOperation(action, branch_type=0).frame()['branch_type'] == 0
    assert RasOperation(action, start_pc=(1 << 51) - 1, position=15, enable=0).frame() == dict(
        action=action, branch_type=branch_type, start_pc=(1 << 51) - 1, position=15, enable=0)


@pytest.mark.parametrize('pc', (-2, -1, 1, 3, 1 << 50, True, None, '0x1000'))
def test_invalid_cfi_pc_is_rejected_before_any_drive(pc):
    with pytest.raises(ValueError, match='cfi_pc'):
        encode_cfi_pc(pc)


@pytest.mark.parametrize('pc', (0, 2, 0x9804800E, (1 << 49) - 2, 1 << 49, (1 << 50) - 2))
def test_cfi_pc_encoding_prunes_only_alignment_bit_not_sign(pc):
    assert encode_cfi_pc(pc) * 2 == pc


@pytest.mark.parametrize('method,kwargs', (
    ('act', dict(action=2)), ('act_many', dict(operations=(RasOperation(2),))),
    ('restore', dict(meta={})), ('recover', dict(meta={}, action=2)),
))
async def test_operation_requires_started_execution(method, kwargs):
    agent = object.__new__(RasAgent)
    agent._started = False
    with pytest.raises(RuntimeError, match='active Execution'):
        await getattr(agent, method)(**kwargs)


@pytest.mark.parametrize('operations', ((), ({'action': 2},), (RasOperation(2), None)))
async def test_invalid_burst_fails_before_monitor_or_native_access(operations):
    agent = object.__new__(RasAgent)
    agent._started = True
    with pytest.raises(ValueError, match='non-empty sequence'):
        await agent.act_many(operations)


def test_committed_monitor_requires_actual_capability_not_silent_skip():
    with pytest.raises(RuntimeError, match='picker --rw mem_direct'):
        RasCommittedMonitor(SimpleNamespace(dut=SimpleNamespace()))


def test_committed_monitor_requires_unique_native_bindings(tmp_path):
    with pytest.raises(RuntimeError, match='needs one memory-direct binding'):
        RasCommittedMonitor(SimpleNamespace(dut=native_name_dut(tmp_path)))


async def test_observation_requires_started_execution():
    agent = object.__new__(RasAgent)
    agent._started = False
    with pytest.raises(RuntimeError, match='active Execution'):
        async with agent.observe_committed():
            raise AssertionError('unreachable')


MATRICES = (
    ('committed', committed_coverage, [dict(slot=slot, mode=mode) for slot, mode in product(range(8), ('normal', 'saturated'))]),
    ('adjacent', adjacent_coverage, [dict(scenario=case['label']) for case in cases()]),
    ('redirect', redirect_coverage, [dict(storage=storage, counter=counter, redo=redo) for storage, counter, redo in product(
        ('inflight', 'committed'), (0, 3, 7), ('call-same', 'call-distinct-positive', 'call-distinct-negative', 'return'))]),
)


@pytest.mark.parametrize('name,missing', [(name, missing) for name, _, rows in MATRICES for missing in range(len(rows))])
def test_every_supported_coverage_bin_is_required(name, missing):
    _, factory, rows = next(row for row in MATRICES if row[0] == name)
    coverage = factory()
    for index, row in enumerate(rows):
        if index != missing:
            coverage.sample(row)
    with pytest.raises(AssertionError):
        coverage.assert_coverage(100.0)
    coverage.sample(rows[missing])
    coverage.assert_coverage(100.0)
