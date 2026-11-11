"""Four-way owner intent and real zero tag, never learned from response ways."""
import pytest
from suites.frontend.bpu.testbenches.mbtb.model.shared_service import PROGRAMS
from suites.frontend.bpu.testbenches.mbtb.model.shared_service import shared_service_owners
from suites.frontend.bpu.testbenches.mbtb.model.shared_service import shared_service_addresses
from suites.frontend.bpu.testbenches.mbtb.model.replacement import MbtbFourWayLru
from suites.frontend.bpu.testbenches.mbtb.model.semantic import coordinate
from suites.frontend.bpu.testbenches.mbtb.model.semantic import tag


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
def test_nomination_and_logical_owner_follow_the_declared_training_prefix(program):
    neighbor=MbtbFourWayLru();original=neighbor.allocate();extra=neighbor.allocate()
    assert (original,extra)==(3,2)
    if program.shared:neighbor.touch(original)
    state=program.state();plan=program.owners
    assert (state['source_nomination'],state['logical_correction_owner'])==(
        neighbor.victim if program.shared else extra,original if program.shared else extra)
    assert (plan.original,plan.extra,plan.keep,plan.clear,plan.capacity)==(3,2,2,3,4)
    assert plan.nomination!=plan.clear
    assert (plan.correction==plan.clear) is program.shared


@pytest.mark.parametrize('identity_tag',(0,1))
def test_inputs_really_have_the_declared_tag_and_distinct_rows_in_one_bank(identity_tag):
    first,neighbor,target=shared_service_addresses(identity_tag)
    assert coordinate(first)==(0,0,0) and coordinate(neighbor)==(0,0,1)
    assert tag(first)==tag(neighbor)==identity_tag
    assert neighbor-first==128 and first//(1<<20)==target//(1<<20)


@pytest.mark.parametrize('bad',(0,1,None,'shared'))
def test_owner_intent_does_not_coerce_encoded_values(bad):
    with pytest.raises(ValueError):shared_service_owners(bad)


@pytest.mark.parametrize('bad',(False,True,2,-1,None))
def test_address_plan_rejects_an_undeclared_identity(bad):
    with pytest.raises(ValueError):shared_service_addresses(bad)
