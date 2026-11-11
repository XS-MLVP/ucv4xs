"""A prepared expected profile cannot masquerade as actual lookup metadata."""
from types import SimpleNamespace
import pytest
from suites.frontend.bpu.testbenches.mbtb.tests.scenarios.replacement_scenario import checked_feedback_source


@pytest.mark.parametrize('wrong',(False,True))
async def test_replacement_feedback_reads_the_real_source_and_checks_it_before_returning(wrong):
    calls=[]
    metadata=(({'counter_value':3 if wrong else 2},),)
    actual=SimpleNamespace(entries=(),meta_entries=metadata)
    expected=dict(entries=(),meta_entries=(({'counter_value':2},),))
    async def predict(pc):calls.append(pc);return actual
    agent=SimpleNamespace(predict=predict)
    if wrong:
        with pytest.raises(AssertionError):await checked_feedback_source(agent,0x80000000,expected)
    else:
        assert await checked_feedback_source(agent,0x80000000,expected) is actual
    assert calls==[0x80000000]
