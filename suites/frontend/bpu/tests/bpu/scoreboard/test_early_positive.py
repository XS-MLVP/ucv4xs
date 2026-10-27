"""Two-polarity semantic program; synthetic actuals earn no DUT coverage."""
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest

from bpuverify.bpu.checker.early_positive import EarlyPositiveChecks
from bpuverify.bpu.coverage.early_positive import EarlyPositiveCoverage,EXTRA_RULES
from bpuverify.bpu.model.early_opposition import ahead_owner,steady_history,provider
from bpuverify.bpu.model.selection import Kind
from tests.bpu.scoreboard.test_early_opposition import Program as NegativeProgram


class Program(NegativeProgram):
    def make_checks(self,pc,tag_class):return EarlyPositiveChecks(EarlyPositiveCoverage(),pc)

    def declared(self):
        negative=self.opposed();self.checks.opposed_consumer(negative)
        self.checks.protect_seed();return negative

    def prepared_positive(self):
        negative=self.declared()
        negative=self.until(negative,lambda token:ahead_owner(self.model.sources,token) is not None
            and ahead_owner(self.model.sources,token)[1]==0 and steady_history(token,4))
        self.checks.negative_base_source(negative)
        positive=self.steer(negative,3);self.checks.main_positive(positive);return positive

    def positive(self,*,settle=True):
        prepared=self.prepared_positive();self.enable(True)
        return self.until(prepared,lambda token:self.checks.qualifies_current_source(self.model.sources,token),settle=settle)


def checked_ticks(coverage):
    point=coverage.groups['checked'].report()['points'][0]
    return [value['first']['tick'] for origins in point['provenance'].values() for value in origins.values()]


def test_both_polarities_have_distinct_sources_and_actual_useful_confirmation():
    program=Program();source=program.positive();checks=program.checks
    assert checks.negative_confirmed and checks.confirmed_increases
    assert {row[0] for row in checks.negative_confirmed}.isdisjoint(row[0] for row in checks.confirmed_increases)
    assert checks.pool_declared and len(checks.protected_positive)>1
    assert checks.coverage.groups['checked'].coverage==0
    checks.positive_consumer(source);checks.finish_positive(program.named)
    assert checks.closed and all(group.coverage==100 for group in checks.coverage.groups.values())
    assert not checks.pipeline.source_receipts and len(program.retired)==len(set(program.retired))
    assert min(checked_ticks(checks.coverage))>=max(row[2] for row in checks.confirmed_increases)


@pytest.mark.parametrize('fault',('no-negative-proof','no-seed-confirmation','pending-seed','pending-negative-write','no-positive-resident','useful-full','repeat-declaration'))
def test_positive_pool_needs_independent_learning_and_mature_negative_proof(fault):
    program=Program();negative=program.opposed();checks=program.checks;checks.opposed_consumer(negative)
    if fault=='no-negative-proof':checks.confirmed_increases.clear()
    elif fault=='no-seed-confirmation':checks.seeds.clear()
    elif fault=='pending-seed':checks.pending_seeds=[next(iter(checks.seeds.values()))]
    elif fault=='pending-negative-write':checks.pending_effect=('not-yet-compared',)
    elif fault in ('no-positive-resident','useful-full'):
        for key,seed in checks.seeds.items():
            if fault=='no-positive-resident':checks.seeds[key]=replace(seed,entry=replace(seed.entry,tag=seed.entry.tag^128))
            else:program.model.sources.short.useful[key[0]][key[1]]=3
    else:checks.protect_seed()
    with pytest.raises(AssertionError) as first:checks.protect_seed()
    with pytest.raises(AssertionError) as repeated:checks.finish_positive()
    assert repeated.value is first.value and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('no-preparation','too-early','wrong-position','wrong-target','wrong-kind','not-taken','wrong-source',
    'unknown-key','uncompared-owner','wrong-owner-key','extra-repair'))
def test_bad_positive_public_consumer_never_gets_checked_credit(fault):
    program=Program();source=program.positive();checks=program.checks
    if fault=='no-preparation':checks.positive_prepared=None
    elif fault=='too-early':source=NS(token=source.token,prediction_tick=checks.positive_prepared.meta_tick,meta_tick=source.meta_tick)
    elif fault=='unknown-key':checks.protected_positive.clear()
    elif fault=='uncompared-owner':checks.opposed_owners.clear()
    elif fault=='wrong-owner-key':checks.positive_owners[source.token.sequence]=(-1,-1)
    elif fault=='extra-repair':program.corrections[source.token.sequence]=[(source.prediction_tick+2,2)]
    else:
        token=source.token
        if fault=='wrong-source':token=replace(token,early=replace(token.early,source='ahead'))
        else:
            field,value={'wrong-position':('position',4),'wrong-target':('target',program.pc+2),
                'wrong-kind':('kind',Kind.DIRECT),'not-taken':('taken',False)}[fault]
            token=replace(token,early=replace(token.early,branch=replace(token.early.branch,**{field:value})))
        source=NS(token=token,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick)
    with pytest.raises(AssertionError) as first:checks.positive_consumer(source)
    with pytest.raises(AssertionError) as repeated:checks.finish_positive()
    assert repeated.value is first.value and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('no-consumer','no-negative-confirmation','no-positive-confirmation','wrong-source-confirmation',
    'pending-seed','pending-effect','old-source-rebased'))
def test_two_polarity_closure_requires_its_own_named_positive_source(fault):
    program=Program();source=program.positive();checks=program.checks
    if fault!='no-consumer':checks.positive_consumer(source)
    if fault=='no-negative-confirmation':checks.negative_confirmed=()
    elif fault=='no-positive-confirmation':checks.confirmed_increases.clear()
    elif fault=='wrong-source-confirmation':checks.confirmed_increases=[(-1,*row[1:]) for row in checks.confirmed_increases]
    elif fault=='pending-seed':checks.pending_seeds=[checks.seed]
    elif fault=='pending-effect':checks.pending_effect=('not-compared',)
    elif fault=='old-source-rebased':checks.seed=replace(checks.seed,snapshot=replace(checks.seed.snapshot,end_position=15))
    with pytest.raises(AssertionError):checks.finish_positive(program.named)
    assert not checks.closed and not program.retired and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('entry','useful','early-source'))
def test_main_only_positive_preparation_preserves_every_declared_seed(fault):
    program=Program();negative=program.declared();checks=program.checks
    negative=program.until(negative,lambda token:ahead_owner(program.model.sources,token) is not None
        and ahead_owner(program.model.sources,token)[1]==0 and steady_history(token,4))
    checks.negative_base_source(negative)
    prepared=program.steer(negative,3)
    if fault=='early-source':prepared=NS(token=prepared.token,prediction_tick=negative.meta_tick,meta_tick=prepared.meta_tick)
    else:
        key=next(iter(checks.protected_positive));seed,entry,useful=checks.protected_positive[key]
        checks.protected_positive[key]=(seed,replace(entry,counter=entry.counter^1),useful) if fault=='entry' else (seed,entry,useful^1)
    with pytest.raises(AssertionError):checks.main_positive(prepared)
    assert not checks.direction_taken and checks.coverage.groups['checked'].coverage==0


def test_source_tag_and_key_are_checked_against_pool_declared_before_driving():
    program=Program();source=program.positive();checks=program.checks
    value=provider(program.model.sources,source.token);seed,entry,useful=checks.protected_positive[value.key]
    checks.protected_positive[value.key]=(replace(seed,entry=replace(seed.entry,tag=seed.entry.tag^128)),entry,useful)
    with pytest.raises(AssertionError):checks.positive_consumer(source)
    assert checks.coverage.groups['checked'].coverage==0
