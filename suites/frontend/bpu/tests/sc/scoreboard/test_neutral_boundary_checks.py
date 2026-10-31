"""Layer integration with a pure backend, not native/DUT verification."""
from contextlib import asynccontextmanager
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.models.folded_history import PHR_FOLD_LAYOUT
from suites.frontend.bpu.sc.agent.main import ScAgent
from suites.frontend.bpu.sc.model.semantic import Events, ScReference
from suites.frontend.bpu.sc.transaction.types import ScLookup, ScPrediction

PROFILES = tuple((a, b) for a in ('lower', 'upper') for b in ('original-slots', 'exchanged-slots'))


@pytest.fixture
def candidate():
    from suites.frontend.bpu.sc.model import neutral_boundary as model
    from suites.frontend.bpu.sc.checker import neutral_boundary as checker
    from suites.frontend.bpu.sc.coverage import neutral_boundary as coverage
    from suites.frontend.bpu.sc.env import neutral_boundary as env
    from suites.frontend.bpu.sc.case import neutral_boundary as case
    return NS(model=model, checker=checker, coverage=coverage, env=env, case=case)


class Result:
    def __init__(self, sequence, request, actual, accepted, completed):
        self.sequence_id, self.request, self.actual = sequence, request, actual
        self.accepted_event, self.completed_event = NS(tick=accepted), NS(tick=completed)

    def __await__(self):
        async def result():
            return self.actual
        return result().__await__()


class PureAgent:
    """Independent cycle model behind only the real agent's used interface.

    No native model, pin, clock backend, driver or monitor is instantiated.
    The real public-port encoder is used for fake observation data, while
    the candidate's complete expected payload is independently hand-shaped.
    """
    def __init__(self, fault=None):
        self.fault = fault
        self.ports = NS(training=NS(bits=NS(branches=(None,) * 16,
            path_history=(None,) * len(PHR_FOLD_LAYOUT), mbtb_meta=((None,)*5,)*2)))
        self.frames = None

    async def reset(self):
        self.model, self.tick, self.sequence = ScReference(), 0, 0
        self.transfers = []
        self.neutral_seen, self.reverse_count, self.seed_count = False, 0, 0
        self.primary_pc = None

    def advance(self, event=Events()):
        self.model.advance(event)
        self.tick += 2

    def submit_predict_branches(self, pc, layout):
        if self.primary_pc is None:
            self.primary_pc = pc
        accepted = self.tick + 2
        self.advance(Events(pc=pc))
        self.advance(Events(advance=True))
        self.advance(Events(select=True, branches=layout))
        prediction = self.model.prediction
        meta = prediction.metadata()
        names = ('scPathTakenVec', 'scGlobalTakenVec', 'scBWTakenVec', 'scImliTakenVec', 'scBiasTakenVec')
        meta['debug'] = {name: tuple(parts[i] for parts in prediction.components) for i, name in enumerate(names)}
        if self.fault == 'one-family-bias' and self.reverse_count == 31 and pc == self.primary_pc:
            signs = meta['debug']['scPathTakenVec']
            meta['debug']['scPathTakenVec'] = (1 - signs[0], 1 - signs[1], *signs[2:])
        actual = ScPrediction(prediction.directions[0], prediction.used[0], meta, prediction.directions, prediction.used)
        number = self.sequence
        if self.fault == 'duplicate-source' and len(self.transfers) == 1:
            number = self.transfers[0].sequence_id
        completed = accepted if self.fault == 'stale-response' else self.tick
        result = Result(number, ScLookup(pc, 0, 0, branches=layout), actual, accepted, completed)
        self.sequence += 1
        self.transfers.append(result)
        return result

    async def predict_branches(self, pc, layout):
        return await self.submit_predict_branches(pc, layout)

    async def drain_predictions(self):
        return None

    async def check_thresholds(self, wanted):
        assert self.model.thresholds.values == wanted, ('complete threshold mismatch', self.model.thresholds.values, wanted)

    @asynccontextmanager
    async def observe_feedback(self):
        assert self.frames is None
        self.frames = []
        try:
            yield self.frames
        finally:
            self.frames = None

    async def train_batch(self, transaction):
        neutral = len(transaction.branches) == 2
        if neutral:
            self.neutral_seen = True
        elif self.neutral_seen:
            self.reverse_count += 1
        else:
            self.seed_count += 1
        encoded = ScAgent._encode_batch_training(self, transaction)
        if neutral and self.fault == 'wrong-resolved-slot':
            encoded = deepcopy(encoded)
            encoded['branches'][1]['position'] = 9
        if not (neutral and self.fault == 'missing-input'):
            self.frames.append(NS(event=NS(tick=self.tick + 2), value=deepcopy(dict(valid=1, ready=1, bits=encoded))))
        skip = (self.fault == 'missing-recovery' and self.reverse_count == 1 or
                self.fault == 'missing-endpoint-seed' and self.seed_count == 1)
        self.advance(Events() if skip else Events(feedback=transaction))
        capacity = max(len(cache.rows) for family in self.model.writes for cache in family)
        for _ in range(2 + capacity):
            self.advance()
            if self.model.learning is None and not self.model.pending and all(
                    row is None or not row.dirty for family in self.model.writes for cache in family for row in cache.rows):
                break
        else:
            raise AssertionError('pure model feedback did not retire')
        if neutral and self.fault == 'mutated-original':
            self.transfers[0].actual.meta['scPred'] = (0, 1, 1, 1)


def hit_bins(group):
    return sum(bool(value) for point in group.report()['points'] for value in point['counts'].values())


@pytest.mark.asyncio
@pytest.mark.parametrize('boundary,placement', PROFILES)
async def test_complete_candidate_reuses_real_source_ledger_and_complete_port_codec(candidate, boundary, placement):
    program = candidate.model.NeutralBoundaryProgram(boundary, placement)
    coverage = candidate.coverage.NeutralBoundaryCoverage()
    await candidate.case.check_neutral_boundary(PureAgent(), program, coverage)
    evidence = coverage.evidence
    assert evidence['closed'] and evidence['status'] == 'PASS'
    assert evidence['originals'] == evidence['consumed'] == len(evidence['actual_feedbacks']) == program.cold_source_count + 32
    assert set(evidence['recovery_consumers']) == {31, 32}
    assert hit_bins(coverage.groups['reached']) == hit_bins(coverage.groups['checked']) == len(candidate.model.RULES)
    assert len(coverage.groups['checked'].report()['points'][0]['counts']) == 4 * len(candidate.model.RULES)


@pytest.mark.asyncio
@pytest.mark.parametrize('boundary,placement', PROFILES)
@pytest.mark.parametrize('fault', ('duplicate-source', 'stale-response', 'missing-input', 'wrong-resolved-slot',
    'one-family-bias', 'mutated-original', 'missing-recovery', 'missing-endpoint-seed'))
async def test_incomplete_or_incorrect_program_never_gets_checked_credit(candidate, boundary, placement, fault):
    program = candidate.model.NeutralBoundaryProgram(boundary, placement)
    coverage = candidate.coverage.NeutralBoundaryCoverage()
    with pytest.raises(AssertionError):
        await candidate.case.check_neutral_boundary(PureAgent(fault), program, coverage)
    assert coverage.evidence['status'] == 'FAIL' and not coverage.evidence['closed']
    assert hit_bins(coverage.groups['checked']) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('missing', (
    'distinct-originals', 'shared-parameter-identity', 'executed-prefix', 'original-eligibility',
    'qualified-boundary-history', 'neutral-feedback-retained', 'slot-placement-independent',
    'fresh-reverse-learning', 'exact-recovery-consumers', 'unrelated-experience-retained'))
async def test_finish_rejects_each_missing_semantic_obligation(candidate, missing):
    program = candidate.model.NeutralBoundaryProgram('lower', 'original-slots')
    checks = candidate.checker.NeutralBoundaryChecks(program)
    coverage = candidate.coverage.NeutralBoundaryCoverage()
    await candidate.env.NeutralBoundaryEnv(PureAgent(), program, checks, coverage).run()
    checks.completed.remove(missing)
    with pytest.raises(AssertionError):
        checks.finish()
    assert not checks.closed and hit_bins(coverage.groups['checked']) == 0
