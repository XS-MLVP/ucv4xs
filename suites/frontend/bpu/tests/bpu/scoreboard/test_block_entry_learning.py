"""Independent instruction-entry programs and missing-proof controls, no DUT credit."""
import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from bpuverify.bpu.model.block_entry_learning import PROFILES, RULES, program
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.checker.block_entry_learning import Checks
from bpuverify.bpu.coverage.block_entry_learning import Coverage
from tests.bpu.scoreboard.test_early_direction_checking import Program as LearningProgram


class Program(LearningProgram):
    def __init__(self,profile):
        self.profile=profile; super().__init__(program(profile).pc)
    def make_checks(self,pc,tag_class): return Checks(Coverage(self.profile),self.profile)


@pytest.mark.parametrize('profile',PROFILES)
def test_interior_entry_closes_original_learning_and_complete_fresh_consumer(profile):
    p=Program(profile); source=p.learned(); checks=p.checks
    assert checks.coverage.groups['checked'].coverage == 0
    checks.negative_consumer(source); checks.finish()
    assert checks.closed and checks.coverage.closed and checks.coverage.groups['checked'].coverage == 50
    value=checks.snapshot(); assert value['consumer']['pc'] == program(profile).pc
    assert value['consumer']['provider']['table'] == 0 and value['consumer']['provider']['counter'] == 3
    assert value['consumer']['exact'] == dict(position=4,target=program(profile).pc,kind=Kind.DIRECT,taken=True,action=0)


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('fault',('aligned-down','copied-original'))
def test_aligned_entry_or_equal_copied_original_cannot_claim_consumption(profile,fault):
    p=Program(profile); source=p.learned(); token=source.token
    token=replace(token,pc=0x40000000) if fault=='aligned-down' else replace(token)
    source=NS(token=token,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick)
    with pytest.raises(AssertionError): p.checks.negative_consumer(source)
    assert p.checks.coverage.groups['checked'].coverage == 0 and p.checks.witness is None


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('fault',('position','target','kind','taken'))
def test_complete_later_branch_is_required_not_only_an_nt_counter(profile,fault):
    p=Program(profile); source=p.learned(); branch=source.token.middle.branch
    changes=dict(position=2) if fault=='position' else dict(target=0x40000000) if fault=='target' else dict(kind=Kind.CONDITIONAL) if fault=='kind' else dict(taken=False)
    with pytest.raises(AssertionError): p.checks.complete_final(replace(branch,**changes))
    assert p.checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('missing',('allocation','fresh-consumer','original-snapshot','original-fasttrain'))
def test_source_chain_cannot_close_with_any_missing_proof(profile,missing):
    p=Program(profile); source=p.learned(); checks=p.checks
    if missing=='allocation': checks.allocations.clear()
    with pytest.raises(AssertionError):
        if missing!='fresh-consumer': checks.negative_consumer(source)
        if missing=='original-snapshot': checks.old_snapshot=replace(checks.old_snapshot,end_position=15)
        if missing=='original-fasttrain': checks.reached_rules.discard(RULES[4])
        checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0 and not checks.closed


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('missing',RULES)
def test_atomic_coverage_requires_all_actual_learning_obligations(profile,missing):
    coverage=Coverage(profile)
    for rule in RULES:
        if rule!=missing: coverage.record('reached',rule,10); coverage.record('checked',rule,20)
    with pytest.raises(AssertionError): coverage.finish()
    assert coverage.groups['checked'].coverage == 0


def test_entry_case_does_not_expose_raw_io_or_clock_edges():
    for name in ('bpuverify/bpu/case/block_entry_learning.py','tests/bpu/testcase/test_block_entry_learning.py'):
        tree=ast.parse(Path(name).read_text()); forbidden={'ClockCycles','RisingEdge','FallingEdge','get_','set_','gather','create_task'}
        assert not {n.id for n in ast.walk(tree) if isinstance(n,ast.Name)} & forbidden
        assert not {n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)} & forbidden
