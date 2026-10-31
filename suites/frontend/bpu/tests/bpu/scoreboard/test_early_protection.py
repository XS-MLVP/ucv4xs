from suites.frontend.bpu.bpu.model.early_opposition import FALLBACK
"""Semantic strength ledger and synthetic actual comparisons; no DUT credit."""
import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import asyncio

import pytest

from suites.frontend.bpu.bpu.checker.early_direction import live_values, fast_values
from suites.frontend.bpu.bpu.checker.early_protection import EarlyProtectionChecks
from suites.frontend.bpu.bpu.coverage.early_protection import EarlyProtectionCoverage
from suites.frontend.bpu.bpu.model.early_protection import Identity, ProtectionLedger, EDGES, guidance, rules, next_edge, ProtectionEvent
from suites.frontend.bpu.bpu.model.early_opposition import provider, resident, ahead_owner, main_counter, steady_history
from suites.frontend.bpu.bpu.model.early_aging import require_recovery_window
from suites.frontend.bpu.bpu.model.pipeline import Redirect
from suites.frontend.bpu.bpu.driver.recovery import RecoveryDriver
from suites.frontend.bpu.utage.model.semantic import Context, Feedback, Source, tag
from tests.bpu.scoreboard.test_early_opposition import Program as SourceProgram
from tests.bpu.scoreboard.test_early_direction_checking import actual_live, actual_fast
from tests.bpu.scoreboard.test_early_positive import checked_ticks


def semantic_feedback(**changes):
    source = Source(True, 2, True, 1, 0, False, True)
    f = Feedback(0x40000000, Context(), (0, 0), (source,), 4, True, 2)
    return replace(f, **changes)


class Program(SourceProgram):
    def __init__(self, mode):
        self.mode = mode
        self.restore_ages = []
        super().__init__()

    def make_checks(self, pc, tag_class):
        return EarlyProtectionChecks(EarlyProtectionCoverage(), self.mode, pc)

    def step(self, event=None, *, mutate=None):
        event = self.event if event is None else event
        if event.redirect is not None:
            require_recovery_window(self.model.history.taken_edges, event.redirect.source.taken_edges,
                capacity=532, history_bits=397, shift=2)
            self.restore_ages.append(self.model.history.taken_edges-event.redirect.source.taken_edges)
        cycle = self.model.evaluate(event); self.tick += 2
        observed = actual_live(self.model.sources, cycle.enabled[1])
        if mutate is not None:
            mutate(observed)
        self.checks.candidates(dict(observed=dict(early_direction=observed)), event, cycle,
                               self.model, 'synthetic', None)
        self.checks.reached(self.tick)
        expected, actual = live_values(self.model.sources, cycle.enabled[1], observed)
        try:
            self.checks.check(expected, actual, 'complete synthetic actual protection comparison')
            expected, actual = fast_values(self.model.sources, cycle, actual_fast(self.model.sources, cycle))
            self.checks.check(expected, actual, 'complete original source guidance comparison')
        except Exception as error:
            self.checks.failure = error
            raise
        for token, stage, repair in ((cycle.tokens[1], 2, cycle.middle_repair),
                                     (cycle.tokens[2], 3, cycle.final_repair)):
            if token is not None and repair:
                self.corrections.setdefault(token.sequence, []).append((self.tick, stage))
        self.model.advance(event)
        self.checks.checked(self.tick)
        return cycle

    def quiet(self):
        idle = SourceProgram.quiet(self)
        for _ in range(32):
            if (self.checks.pending is None and self.model.sources.short.offered is None
                    and self.model.sources.short.learning is None):
                return idle
            self.step(idle)
        raise AssertionError('all actual comparison obligations must drain')

    def restore_flow(self, source):
        self.quiet()
        # The two existing drivers launch ready and redirect together after
        # drain, then own their normal commit/return and deassertion stages.
        self.step(replace(self.event, redirect=Redirect(source.token.history, (self.pc//16)*16+FALLBACK, self.pc, True)))
        self.step()  # PulseDriver deassertion; not an empirical settling delay.

    def until(self, source, predicate, *, settle=True):
        self.restore_flow(source)
        for _ in range(256):
            token = self.step().metadata
            if token is not None and token.pc==self.pc and predicate(token):
                result = self.receipt(token)
                if settle:
                    self.quiet()
                return result
        raise AssertionError('flowing recovery did not produce the declared semantic source')

    def query(self, source):
        return self.until(source, lambda token: True)

    def repeat_opposed(self, source):
        c = self.checks
        before = resident(self.model.sources, c.identity.key), c.ledger.protection
        source = self.steer(source, 3); self.enable(True)
        source = self.until(source, lambda token: main_counter(token)==3 and steady_history(token, 2)
            and (owner := ahead_owner(self.model.sources, token)) is not None and owner[1]==3
            and self.model.sources.short_snapshot(token).prediction.frame.read.indices[c.identity.table] != c.identity.index)
        c.preserved_other_history(source, before)
        source = self.steer(source, 0); self.enable(True)
        return self.until(source, lambda token: (v := provider(self.model.sources, token)) is not None
            and (v.key, v.tag)==(c.identity.key, c.identity.tag) and v.counter < 4 and v.base)

    def wrong(self, source, edge):
        c = self.checks
        before = resident(self.model.sources, c.identity.key), c.ledger.protection
        source = self.steer(source, 3)
        c.preserved_other_history(source, before)
        self.enable(False)
        for _ in range(8):
            source = self.query(source)
            if steady_history(source.token, FALLBACK):
                break
        else:
            raise AssertionError('fresh original NT suffix required')
        self.enable(True)
        return self.until(source, lambda token: edge in c.confirmed and main_counter(token)==3 and steady_history(token, 2))

    def complete(self):
        c = self.checks
        if self.mode in ('upper-hold', 'upper-release'):
            source = self.opposed(); c.opposed_consumer(source)
            source = self.repeat_opposed(source)
            assert 'upper-hold' in c.confirmed
            if self.mode == 'upper-release':
                source = self.wrong(source, 'upper-release')
                source = self.steer(source, 0); self.enable(True)
                source = self.until(source, lambda token: (v := provider(self.model.sources, token)) is not None
                    and v.key==c.identity.key and v.tag==c.identity.tag and v.counter < 4)
        else:
            source = self.strong()
            for edge in ('toward-lower', 'reach-lower', 'lower-hold'):
                source = self.wrong(source, edge)
            source = self.steer(source, 0); self.enable(True)
            source = self.until(source, lambda token: 'lower-recover' in c.confirmed
                and (v := provider(self.model.sources, token)) is not None and v.key==c.identity.key
                and v.tag==c.identity.tag and v.counter < 4)
        source = self.until(source, lambda token: (v := provider(self.model.sources, token)) is not None
            and (v.key, v.tag, v.position)==(c.identity.key, c.identity.tag, c.identity.position) and v.counter < 4)
        c.fresh_consumer(source); self.quiet()
        return source


@pytest.mark.parametrize('mode', tuple(EDGES))
def test_normal_original_source_program_confirms_limits_and_reverse_without_state_seeding(mode):
    p = Program(mode); p.complete(); c = p.checks
    assert c.pending is None and set(c.confirmed)=={e[0] for e in EDGES[mode]}
    assert all(written+2==actual for event, written, actual in c.confirmed.values())
    assert all(event.owner in c.ledger.owners for event, _, _ in c.confirmed.values())
    assert max(p.restore_ages) <= 10
    assert c.boundaries.groups['checked'].coverage == 0
    c.finish_boundaries(p.named)
    checked = c.boundaries.groups['checked'].report()['points'][0]
    assert c.boundaries.groups['checked'].coverage == pytest.approx(100*len(rules(mode))/25)
    assert min(checked_ticks(c.boundaries)) >= max(row[2] for row in c.confirmed.values())
    assert min(checked_ticks(c.boundaries)) >= c.last_actual_tick


@pytest.mark.parametrize('kind,protection,after', (
    ('reward', 3, 3), ('penalty', 0, 0), ('penalty', 3, 2), ('reward', 0, 1),
    ('neutral', 2, 2)))
def test_semantic_strength_edges_do_not_wrap_or_lock_at_limits(kind, protection, after):
    ledger = ProtectionLedger(counter=2, protection=protection)
    event = ledger.apply(11, False, kind)
    assert (event.before, event.after, event.counter_before, event.counter_after)==(protection,after,2,1)
    with pytest.raises(ValueError): ledger.apply(11, False, kind)


@pytest.mark.parametrize('changes', ({'position': 1}, {'kind': 2, 'position': 2},
    {'sources': (Source(False, 2, True, 1, 0, False, True),)},
    {'sources': (Source(True, 2, False, 1, 0, False, True),)},
    {'sources': (Source(True, 2, True, 0, 0, False, True),)},
    {'indices': (0, 1)}, {'context': Context.from_recent(1)}))
def test_wrong_identity_unexecuted_or_nonconditional_source_cannot_learn_protection(changes):
    identity = Identity(1, 0, tag(0x40000000, Context(), 1), 2)
    assert guidance(semantic_feedback(**changes), identity) is None


def test_guidance_role_depends_on_original_prediction_actual_outcome_and_base():
    identity = Identity(1, 0, 0, 2)
    assert guidance(semantic_feedback(), identity)==(False,'reward')
    assert guidance(semantic_feedback(position=2, taken=True, kind=1), identity)==(True,'penalty')
    source = replace(semantic_feedback().sources[0], base=False)
    assert guidance(semantic_feedback(sources=(source,)), identity)==(False,'neutral')


@pytest.mark.parametrize('kwargs', ({'counter': -1}, {'counter': 8}, {'protection': -1},
                                  {'protection': 4}, {'counter': True}))
def test_invalid_strength_is_not_a_legal_model_initial_state(kwargs):
    with pytest.raises(ValueError): ProtectionLedger(**kwargs)


@pytest.mark.parametrize('cell', ((0, 0), (1, 511)))
def test_wrong_untouched_actual_protection_blocks_all_checked_credit(cell):
    p = Program('upper-hold'); p.complete(); c = p.checks
    def corrupt(actual):
        values = [list(row) for row in actual['useful']]
        values[cell[0]][cell[1]] ^= 1
        actual['useful'] = tuple(tuple(row) for row in values)
    before = c.ledger.protection
    with pytest.raises(AssertionError): p.step(p.quiet(), mutate=corrupt)
    assert c.ledger.protection == before and c.boundaries.groups['checked'].coverage == 0


def test_missing_actual_confirmation_or_fresh_consumer_cannot_close():
    p = Program('upper-hold'); p.complete(); c = p.checks
    c.completed.discard('fresh-original-consumer')
    with pytest.raises(AssertionError): c.finish_boundaries(p.named)
    assert c.boundaries.groups['checked'].coverage == 0


def test_protection_ledger_imports_no_actual_driver_or_signal_implementation():
    tree = ast.parse(Path('bpu/model/early_protection.py').read_text())
    assert {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}=={
        'dataclasses', 'suites.frontend.bpu.utage.model.semantic'}
    assert not any(isinstance(n, ast.Import) for n in ast.walk(tree))


@pytest.mark.parametrize('owner', (-1, True, 'not-a-source'))
def test_invalid_source_identity_cannot_consume_a_learning_event(owner):
    with pytest.raises(ValueError): ProtectionLedger().apply(owner, False, 'reward')


def test_recovery_seen_before_lower_hold_cannot_receive_out_of_order_credit():
    event = ProtectionEvent(1, 'reward', 0, 1, 3, 2)
    assert next_edge('lower-recover', {'toward-lower', 'reach-lower'}, event) is None
    assert next_edge('lower-recover', {'toward-lower', 'reach-lower', 'lower-hold'}, event) == 'lower-recover'


def test_expected_write_is_not_credited_before_the_next_complete_actual_comparison():
    p = Program('upper-hold'); source = p.prepared(); p.enable(True)
    p.until(source, lambda token: (v := provider(p.model.sources, token)) is not None
        and v.key==p.checks.identity.key and v.base and v.counter < 4, settle=False)
    for _ in range(32):
        if p.checks.pending is not None and p.checks.pending[2]=='upper-hold':
            break
        p.step()
    else:
        raise AssertionError('normal original source did not schedule upper hold')
    assert 'upper-hold' not in p.checks.confirmed
    def corrupt(actual):
        values = [list(row) for row in actual['useful']]
        key = p.checks.identity.key; values[key[0]][key[1]] ^= 1
        actual['useful'] = tuple(tuple(row) for row in values)
    with pytest.raises(AssertionError): p.step(mutate=corrupt)
    assert 'upper-hold' not in p.checks.confirmed
    assert p.checks.boundaries.groups['checked'].coverage == 0


def test_unassociated_original_guidance_cannot_claim_a_protection_effect():
    p = Program('upper-hold'); p.strong(); p.checks.offers.clear()
    # No fabricated feedback: let another ordinary source mature, then drop
    # only the verification association as a negative control.
    source = p.until(p.checks.strong, lambda token: provider(p.model.sources, token) is not None, settle=False)
    for _ in range(32):
        learning = p.model.sources.short.learning
        if learning is not None and guidance(learning.feedback, p.checks.identity) is not None:
            break
        p.step()
    else:
        raise AssertionError('normal qualified guidance did not mature')
    p.checks.offers.clear()
    with pytest.raises(AssertionError): p.step()
    assert p.checks.boundaries.groups['checked'].coverage == 0


def test_replacing_original_metadata_prevents_boundary_closure():
    p = Program('upper-hold'); p.complete(); c = p.checks
    tick, (source, metadata, snapshot) = next(iter(c.originals.items()))
    c.originals[tick] = (source, {'not-the-original-metadata': True}, snapshot)
    with pytest.raises(AssertionError): c.finish_boundaries(p.named)
    assert c.boundaries.groups['checked'].coverage == 0


def test_case_uses_owned_program_actions_not_edges_or_framework_task_orchestration():
    text = Path('bpu/case/early_protection.py').read_text()
    assert not any(word in text for word in ('ClockCycles', 'RisingEdge', 'FallingEdge', 'asyncio', '.Set('))


@pytest.mark.parametrize('damage', (None, 'duplicate-acceptance', 'wrong-source', 'not-ready', 'old-work'))
async def test_recovery_driver_joins_disjoint_launches_and_requires_one_actual_owned_acceptance(damage):
    p = Program('upper-hold'); source = p.strong(); token = source.token
    source.prediction = NS(start_pc=p.pc)
    source.meta = NS(redirect={'phr': token.history.metadata()})
    receipts = NS(redirect_count=0, last_redirect=None)
    checker = NS(coverage=receipts, source_token=lambda _: token, raise_failure=lambda: None,
        model=NS(history=p.model.history, stages=(None, object() if damage=='old-work' else None, None),
                 sources=NS(main_pending=lambda: False)), plan_redirect=lambda *args: None)
    ready, redirect = asyncio.Event(), asyncio.Event()
    class Agent:
        async def set_ready(self, **values):
            assert values == dict(prediction=True, meta=True)
            ready.set()
            await redirect.wait()
        async def redirect(self, request):
            assert request.payload()['meta'] == source.meta.redirect
            redirect.set()
            await ready.wait()
            receipts.redirect_count += 2 if damage=='duplicate-acceptance' else 1
            origin = replace(token.history) if damage=='wrong-source' else token.history
            receipts.last_redirect = 44, origin, damage!='not-ready'
    async with asyncio.timeout(1):
        if damage is None:
            assert await RecoveryDriver(Agent(), checker).send(source) == 44
        else:
            with pytest.raises((AssertionError, RuntimeError)):
                await RecoveryDriver(Agent(), checker).send(source)
