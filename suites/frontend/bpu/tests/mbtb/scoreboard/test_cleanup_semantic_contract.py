"""Outer semantic receipts must describe the actual four-way cleanup plan."""
from types import SimpleNamespace
import pytest
from suites.frontend.bpu.mbtb.case.semantic import cleanup_zero_key
from suites.frontend.bpu.mbtb.case import cleanup_overlap_scenario


@pytest.mark.parametrize('combined_zero',(False,True))
@pytest.mark.parametrize('clear_way',(3,1))
async def test_receipt_uses_input_planned_clear_not_the_old_two_way_constant(monkeypatch,combined_zero,clear_way):
    reference=SimpleNamespace(input_tick=100,accepted_cleanup=[],raise_failure=lambda:None)
    agent=SimpleNamespace(reference=reference);receipts=[]
    coverage=SimpleNamespace(record=lambda *args,**kwargs:receipts.append((args,kwargs)))

    async def prepared(agent,checkpoint,**kwargs):
        checkpoint.sample(dict(phase='prepared'))
        reference.input_tick+=10
        reference.accepted_cleanup.append(dict(tick=102,align=0,bank=0,
            tag=0 if combined_zero else 1,position=0 if combined_zero else 5,way=clear_way))

    monkeypatch.setattr(cleanup_overlap_scenario,'check_case',prepared)
    if clear_way!=3:
        with pytest.raises(AssertionError):await cleanup_zero_key(agent,coverage,combined_zero=combined_zero)
        assert not receipts
    else:
        await cleanup_zero_key(agent,coverage,combined_zero=combined_zero)
        assert [args[0] for args,_ in receipts]==['reached','checked']
        assert all(row['cleared_way']==3 for _,row in receipts)
        assert receipts[-1][1]['survivor_way']==2
