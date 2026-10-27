"""Pure publication controls cannot produce hardware coverage credit."""
import pytest

from bpuverify.bpu.coverage.main_sibling import Coverage, RULES
from bpuverify.bpu.model.main_sibling import Program, PHASES, ORIGINS



@pytest.mark.parametrize('phase',PHASES)
@pytest.mark.parametrize('origin',ORIGINS)
def test_complete_profile_only_credits_its_declared_eight_obligations_once(phase,origin):
    coverage = Coverage(Program(phase,origin))
    assert len(coverage.counts('checked'))==32
    for rule in RULES:coverage.reached(rule)
    assert not any(coverage.counts('checked').values())
    coverage.finish()
    assert coverage.groups['checked'].coverage==25
    assert {name:count for name,count in coverage.counts('checked').items() if count}=={
        phase+'.'+origin+'.'+rule:1 for rule in RULES}
    before = coverage.counts('checked')
    with pytest.raises(AssertionError):coverage.finish()
    assert coverage.counts('checked')==before


@pytest.mark.parametrize('missing',RULES)
def test_every_actual_lifetime_obligation_precedes_any_checked_credit(missing):
    coverage = Coverage(Program('pending','current'))
    for rule in RULES:
        if rule!=missing:coverage.reached(rule)
    with pytest.raises(AssertionError):coverage.finish()
    assert not any(coverage.counts('checked').values())


def test_duplicate_or_physical_coordinate_is_not_a_new_semantic_obligation():
    coverage = Coverage(Program('pending','current'))
    coverage.reached(RULES[0])
    for rule in (RULES[0],'bank0-way1'):
        with pytest.raises(ValueError):coverage.reached(rule)
    assert not any(coverage.counts('checked').values())
