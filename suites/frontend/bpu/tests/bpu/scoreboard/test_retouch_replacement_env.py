"""Existing driver admission keeps ordering and errors out of testcase code."""
from contextlib import contextmanager
from types import SimpleNamespace as NS

import pytest
from bpuverify.bpu.env.direction_service import DirectionService
from bpuverify.bpu.env.retouch_replacement import RetouchReplacementService
from bpuverify.bpu.bundle.retouch_replacement import retouch_replacement_binding
from bpuverify.bpu.model.tage.forwarding import resolved_path
from bpuverify.tage.model.semantic import TageReference


def test_environment_installs_complete_static_retained_binding(monkeypatch):
    captured=[]
    monkeypatch.setattr(DirectionService,'__init__',lambda self,env,checks,**kw:captured.append(kw))
    RetouchReplacementService(object(),object())
    assert captured==[dict(binding_factory=retouch_replacement_binding)]


@pytest.mark.parametrize('mode',('overlapped','settled'))
@pytest.mark.parametrize('previous_active',(False,True))
async def test_one_async_send_group_respects_capacity_final_maturity_and_foreground_error(monkeypatch,mode,previous_active):
    main=NS(offered=None,directions={(0,0):NS(pending=[]),(1,0):NS(pending=[])})
    tage=TageReference(retention_policy='learning')
    sources=tuple(NS(meta=NS(resolve=object())) for _ in range(6))
    checks=NS(sources=sources,program=NS(mode=mode,branch_outcomes=lambda i:resolved_path()),failure=None,last_launch=None)
    calls=[]
    @contextmanager
    def admit(predicate):
        earlier=NS(resolve_meta=sources[0].meta.resolve)
        assert predicate(earlier)
        main.offered=object();assert not predicate(earlier);main.offered=None
        main.directions[0,0].pending.append(object());assert not predicate(earlier)
        main.directions[0,0].pending.clear()
        checks.failure=AssertionError('first actual mismatch');assert not predicate(earlier);checks.failure=None
        final=NS(resolve_meta=sources[-1].meta.resolve)
        tage.accepted=object() if previous_active else None
        assert predicate(final)==(mode=='overlapped' or not previous_active)
        if mode=='overlapped' or not previous_active:
            assert checks.last_launch==dict(tick=100,learning_inflight=previous_active)
        tage.accepted=None;assert predicate(final)
        calls.append('admitted');yield;calls.append('closed')
    env=NS(agent=NS(training_driver=NS(admit_when=admit)),branch_path=lambda x:x,
           checker=NS(failure=None,last_tick=100,model=NS(sources=NS(main=main,tage=tage))))
    def initialize(self,env,checks,**kw):
        self.env,self.agent,self.checks=env,env.agent,checks;self.monitor=NS(failure=None)
    monkeypatch.setattr(DirectionService,'__init__',initialize)
    service=RetouchReplacementService(env,checks)
    async def submit(requests):
        assert requests==tuple((s,resolved_path()) for s in sources);calls.append('single-send-group')
    service.submit=submit
    await service.submit_program()
    assert calls==['admitted','single-send-group','closed']
