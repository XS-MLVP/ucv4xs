"""Independent directory replay, source/late-fault gates and region geometry."""
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
import pytest
from toffee import CheckContext, Scoreboard, ScoreboardMismatch, ScoreboardMode, Transfer
from suites.frontend.bpu.bpu.coverage.ittage import DIRECTORY_RULES, directory_coverage
from suites.frontend.bpu.bpu.case.ittage_feedback import PC, check_target_feedback
from suites.frontend.bpu.bpu.checker.ittage import check_coherent_target
from suites.frontend.bpu.bpu.checker.ittage_region import RegionChecker
from suites.frontend.bpu.bpu.model.ittage import IttageContextModel
from suites.frontend.bpu.bpu.model.ittage_region import directory_program, feedback_targets, target_regions
from suites.frontend.bpu.bpu.model.sc.model import canonical, encoded_payload
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining, BpuBranchFeedback
from suites.frontend.bpu.ittage.model.region import IttageRegionModel
from tests.bpu.scoreboard.integrated.test_high_index_useful import BootstrapHarness


def transaction(target, *, allocated=True):
    meta = dict(ittage=dict(provider=dict(valid=0), providerCnt_value=0, providerTarget_addr=0,
        allocate=dict(valid=int(allocated), bits=0)))
    return BpuBatchTraining(PC, meta, (BpuBranchFeedback(4, target, 3, mispredict=1),))


class Trace:
    def __init__(self):
        self.model, self.events, self.tick = IttageRegionModel(), [], 41
        self.step(reset=1)

    def sample(self, reset, write, feedback):
        region = 0 if write is None else write
        allocation = deepcopy(self.model).allocate(region << 20)
        requests = (0, 7, 15)
        updates = []
        for queried in (region, 0x817):
            bypass = write is not None and queried == region
            hit = queried in self.model.regions
            pointer = allocation.pointer if bypass else self.model.regions.index(queried) if hit else 0
            updates.append(dict(region=queried, hit=int(hit or bypass), pointer=pointer))
        return dict(reset=reset, state=[dict(valid=int(r is not None), region=r or 0) for r in self.model.regions],
            ports=dict(write_valid=int(write is not None), write_region=region, write_pointer=allocation.pointer,
                requests=requests, responses=[dict(hit=int(self.model.regions[p] is not None),
                    region=self.model.regions[p] or 0) for p in requests], updates=updates),
            target_updates=[dict(valid=0)] * 3, feedback_valid=int(feedback is not None), feedback_ready=1,
            feedback=None if feedback is None else encoded_payload(canonical(asdict(feedback))))

    def step(self, *, reset=0, write=None, feedback=None):
        for phase in ('preedge', 'rising'):
            self.events.append([phase, Transfer(event=SimpleNamespace(tick=self.tick),
                value=self.sample(reset, write, feedback))])
            self.tick += 1
            if phase == 'preedge':
                if reset:
                    self.model = IttageRegionModel()
                elif write is not None:
                    self.model.allocate(write << 20)

    def allocate(self, target):
        tx = transaction(target)
        self.events.append(['plan', tx])
        self.step(feedback=tx)
        self.step(write=target >> 19)


def replay(events):
    checker = RegionChecker()
    for phase, value in events:
        if phase == 'plan':
            checker.plan_feedback(value)
        else:
            checker.observe(phase, value)
    return checker, checker.summary()


def capacity_trace():
    trace = Trace()
    for region in range(0x810, 0x820):
        trace.allocate((region << 19) | 0x90)
    trace.allocate((0x817 << 19) | 0x120)
    trace.allocate((0x830 << 19) | 0x180)
    trace.allocate((0x831 << 19) | 0x240)
    return trace


def test_directory_state_and_PLRU_are_replayed_from_reset_not_observed_pointers():
    _, summary = replay(capacity_trace().events)
    writes = summary['writes']
    assert [row['pointer'] for row in writes[:16]] == list(range(16))
    assert writes[16]['pointer'] == 7 and writes[16]['reused']
    assert [row['pointer'] for row in writes[-2:]] == [8, 0]
    assert [row['evicted_region'] for row in writes[-2:]] == [0x818, 0x810]
    assert summary['frames'] == 78  # Starts at tick41, not an assumed tick1.


@pytest.mark.parametrize('fault', ('region', 'neighbor', 'valid', 'write-pointer', 'read-hit', 'read-region',
    'update-hit', 'update-pointer', 'phase', 'gap', 'reset', 'feedback-payload', 'write-payload', 'missing-effect'))
def test_any_source_or_late_directory_fault_prevents_completion(fault):
    events = deepcopy(capacity_trace().events)
    phase, observation = events[-1]
    row = observation.value
    if fault == 'region': row['state'][0]['region'] ^= 1
    elif fault == 'neighbor': row['state'][15]['region'] ^= 1
    elif fault == 'valid': row['state'][0]['valid'] ^= 1
    elif fault == 'write-pointer': row['ports']['write_pointer'] ^= 1
    elif fault == 'read-hit': row['ports']['responses'][0]['hit'] ^= 1
    elif fault == 'read-region': row['ports']['responses'][0]['region'] ^= 1
    elif fault == 'update-hit': row['ports']['updates'][0]['hit'] ^= 1
    elif fault == 'update-pointer': row['ports']['updates'][0]['pointer'] ^= 1
    elif fault == 'phase': events[-1][0] = 'preedge'
    elif fault == 'gap': observation.event.tick += 2
    elif fault == 'reset': events[0][1].value['reset'] = 0
    elif fault == 'feedback-payload':
        prior = next(value for phase, value in reversed(events) if phase == 'preedge' and value.value['feedback_valid'])
        prior.value['feedback']['branches'][0]['bits']['target_addr'] ^= 1
    elif fault == 'write-payload': events[-2][1].value['ports']['write_region'] ^= 1
    else: events.pop()
    with pytest.raises(ScoreboardMismatch):
        replay(events)


def test_missing_accepted_write_cannot_be_replaced_by_idle_waiting():
    trace = Trace()
    tx = transaction(0x40100090)
    trace.events.append(['plan', tx])
    trace.step(feedback=tx)
    trace.step()
    with pytest.raises(ScoreboardMismatch, match='drained'):
        replay(trace.events)


def test_nonallocation_feedback_must_not_trigger_a_region_write():
    trace = Trace()
    tx = transaction(0x40100090, allocated=False)
    trace.events.append(['plan', tx])
    trace.step(feedback=tx)
    trace.step(write=tx.branches[0].target >> 19)
    with pytest.raises(ScoreboardMismatch, match='unplanned region write'):
        replay(trace.events)


def test_same_PC_region_allocation_does_not_write_the_directory():
    trace = Trace()
    tx = transaction(0x40000090)
    trace.events.append(['plan', tx])
    trace.step(feedback=tx)
    _, summary = replay(trace.events)
    assert not summary['writes'] and summary['regions'] == (None,) * 16


def test_correct_unconfident_provider_suppresses_region_allocation():
    tx = transaction(0x40100090)
    tx.resolve_meta['ittage'].update(provider=dict(valid=1), providerCnt_value=0, providerTarget_addr=tx.branches[0].target)
    checker = RegionChecker()
    checker.plan_feedback(tx)
    assert checker.plans[0][2] is False


def test_program_is_capacity_plus_reuse_and_replacement_not_a_bank_cross_product():
    plan = directory_program()
    assert len(plan) == 21 and len({r['pc'] & 255 for r in plan}) == 21
    assert all((r['pc'] & 7) <= r['position'] for r in plan)
    assert len({r['target'] >> 19 for r in plan if r['role'] == 'fill'}) == 16
    assert [r['role'] for r in plan[-3:]] == ['reuse', 'replace-first', 'replace-second']
    assert plan[9]['role'] == 'reuse-partial' and sum(r['role']=='fill' for r in plan[:9])==8
    assert plan[9]['target'] >> 19 == plan[4]['target'] >> 19


async def test_multiple_source_PCs_share_one_genuine_cold_lead_without_waiting_for_a_second_visit():
    env = BootstrapHarness()
    await env.bootstrap((dict(pc=0x40010006), dict(pc=0x4001000e)))
    assert env.cold == [0x40010000]
    assert set(env.checkpoints) == {0x40010006, 0x4001000e}


@pytest.mark.parametrize('family,status,missing',[(family,status,rule) for family,rules in DIRECTORY_RULES.items()
    for status in ('reached','checked') for rule in rules])
def test_every_directory_contract_is_required(family,status,missing):
    group = directory_coverage(family,status)
    for rule in DIRECTORY_RULES[family]:
        if rule != missing: group.sample(dict(rule=rule))
    with pytest.raises(AssertionError): group.assert_coverage(100)


@pytest.mark.parametrize('pc', (-1, 0, True, (1 << 49) - 1))
def test_bad_target_region_geometry_rejected(pc):
    with pytest.raises(ValueError): target_regions(pc)


@pytest.mark.parametrize('targets', ((), (-1,), (1 << 49,), (True,), (1.5,)))
async def test_bad_feedback_targets_fail_before_any_agent_access(targets):
    with pytest.raises(ValueError): await check_target_feedback(None, None, targets=targets)


@pytest.mark.parametrize('proposal_order', ((0, 1, 2), (0, 2), (1, 2), (2,)))
def test_cross_region_diagnostic_targets_a_previously_allocated_region_for_every_table_order(proposal_order):
    model, regions, proposals, rewritten = IttageContextModel(), IttageRegionModel(), iter(proposal_order), False
    proposal = next(proposals)
    for target in feedback_targets(PC):
        before = model.metadata()
        operations = model.advance(dict(valid=proposal is not None, bits=proposal), target,
            mispredict=model.target() != target)
        if 'allocate' in operations:
            if target >> 19 != PC >> 19: regions.allocate(target << 1)
            proposal = next(proposals, None)
        if 'zero_confidence_target_write' in operations and target >> 19 != PC >> 19:
            assert target >> 19 in regions.regions
            assert before['providerCnt_value'] == 0
            rewritten = True
    assert rewritten


def coherent_row():
    return dict(tick=10, parent=dict(s3_pc=PC, s3_target=42, s3_taken=1),
        boundary=dict(s3=dict(valid=1, prediction=dict(position=4))))


@pytest.mark.parametrize('fault', ('pc', 'target', 'taken', 'position', 'override', 'missing', 'duplicate'))
def test_associated_S3_target_check_rejects_wrong_source_or_output(fault):
    row, rows = coherent_row(), []
    if fault == 'pc': row['parent']['s3_pc'] ^= 1
    elif fault == 'target': row['parent']['s3_target'] ^= 1
    elif fault == 'taken': row['parent']['s3_taken'] = 0
    elif fault == 'position': row['boundary']['s3']['prediction']['position'] = 5
    elif fault == 'override': row['boundary']['s3']['valid'] = 0
    if fault != 'missing': rows.append(row)
    if fault == 'duplicate': rows.append(row)
    transaction = SimpleNamespace(meta_tick=10, prediction=SimpleNamespace(start_pc=PC))
    board = Scoreboard('associated-target')
    with pytest.raises(ScoreboardMismatch):
        check_coherent_target(board, SimpleNamespace(records=rows), transaction, 42, 43, 4,
            CheckContext(board.name, ScoreboardMode.DIRECT))


def test_passive_callback_failure_is_latched_and_raised_in_foreground():
    events = deepcopy(capacity_trace().events)
    events[-1][1].value['state'][0]['region'] ^= 1
    checker = RegionChecker()
    for phase, value in events:
        if phase == 'plan': checker.plan_feedback(value)
        else: checker.capture(phase, value)
    with pytest.raises(ScoreboardMismatch, match='sixteen'):
        checker.raise_failure()
    with pytest.raises(ScoreboardMismatch): checker.summary()


def test_unplanned_accepted_feedback_is_never_inferred_into_expected_state():
    trace = Trace()
    trace.step(feedback=transaction(0x40100090))
    with pytest.raises(ScoreboardMismatch, match='must be planned'):
        replay(trace.events)


def test_reset_must_not_discard_a_preexisting_feedback_plan():
    checker = RegionChecker()
    checker.plan_feedback(transaction(0x40100090))
    with pytest.raises(ScoreboardMismatch, match='discarded by reset'):
        checker.observe(*Trace().events[0])
