"""Pipeline and direction history share one frozen SDK capture, not task order."""
from types import SimpleNamespace as NS
import pytest
from toffee import Bundle,ClockCycles,Execution,MemoryBackend
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.bpu.env import pipeline as module
from suites.frontend.bpu.bpu.checker import common_history as common_module
from tests.framework.fakes import Signal


@pytest.mark.parametrize('with_common',(False,True))
async def test_one_capture_freezes_both_views_before_pipeline_processing_and_stops_on_exit(monkeypatch,with_common):
    clock=object();data=Signal(width=8);data.Set(7);rows=[];order=[];ends=[]
    class Pipeline:
        def __init__(self,*args,**kwargs):self.model=NS(sources=object());self.last_tick=None
        def capture(self,row,event):
            self.last_tick=event.tick;rows.append(('pipeline',event.tick,row['value']))
            order.append('pipeline');data.Set(data.U()+1)
        def finish(self):ends.append('pipeline')
        def raise_failure(self):pass
    class Common:
        def __init__(self,pipeline,**kwargs):self.pipeline=pipeline;self.observe_state=kwargs['observe_state']
        def capture_state(self,event,row):
            assert self.pipeline.last_tick==event.tick and order[-1]=='pipeline'
            order.append('common');rows.append(('common',event.tick,row['value']))
        def raise_failure(self):ends.append('common')
    monkeypatch.setattr(module,'PipelineChecker',Pipeline)
    monkeypatch.setattr(common_module,'CommonHistoryChecks',Common)
    monkeypatch.setattr(module,'pipeline_binding',lambda *a,**kw:PortBinding(clock,Bundle(value=data),'pipeline'))
    from suites.frontend.bpu.bpu.bundle import common_history as binding_module
    monkeypatch.setattr(binding_module,'common_history_binding',lambda *a,**kw:PortBinding(clock,Bundle(value=data),'common'))
    async with Execution(MemoryBackend(clock)) as execution:
        observation=module.PipelineObservation(NS(_execution=execution),with_common_history=with_common)
        async with observation:await ClockCycles(clock,3)
        before=len(rows);await ClockCycles(clock,2);assert len(rows)==before
    assert [(tick,value) for tag,tick,value in rows if tag=='pipeline']==[(2,7),(4,8),(6,9)]
    if with_common:
        assert [(tick,value) for tag,tick,value in rows if tag=='common']==[(2,7),(4,8),(6,9)]
        assert order==['pipeline','common']*3 and ends==['pipeline','common']
    else:assert ends==['pipeline'] and all(tag=='pipeline' for tag,_,_ in rows)
