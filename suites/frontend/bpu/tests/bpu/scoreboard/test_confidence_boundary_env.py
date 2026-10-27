"""Environment wiring and admission contracts, without a DUT or measurements."""
from contextlib import contextmanager
from types import SimpleNamespace as NS

import pytest

from bpuverify.bpu.env.direction_service import DirectionService
from bpuverify.bpu.env.mixed_visibility import MixedVisibilityService
from bpuverify.bpu.env.confidence_boundary import ConfidenceBoundaryService
from bpuverify.bpu.bundle.confidence_boundary import confidence_boundary_binding
from bpuverify.bpu.bundle.partial_residency import partial_residency_binding
from bpuverify.bpu.model.tage.confidence_boundary import PROGRAMS


@pytest.mark.parametrize('custom',(False,True),ids=('old-default','new-complete-observation'))
def test_service_constructor_preserves_default_binding_and_accepts_new_static_bundle(monkeypatch,custom):
    captured=[]
    monkeypatch.setattr(DirectionService,'__init__',lambda self,env,checks,**kw:captured.append((env,checks,kw)))
    env,checks=object(),object()
    (ConfidenceBoundaryService if custom else MixedVisibilityService)(env,checks)
    a,b,kw=captured[0]
    assert a is env and b is checks
    factory=kw['binding_factory']
    if custom:assert factory is confidence_boundary_binding
    else:assert factory.func is partial_residency_binding and factory.keywords==dict(include_hit_ranks=True)


async def test_all_transfers_are_submitted_together_under_existing_driver_capacity_policy(monkeypatch):
    main=NS(offered=None,directions={(0,0):NS(pending=[]),(1,0):NS(pending=[])})
    program=PROGRAMS[2];requests=tuple(object() for _ in range(3+len(program.late_sources)))
    calls=[]
    @contextmanager
    def admit(predicate):
        assert predicate(None)
        main.offered=object();assert not predicate(None);main.offered=None
        main.directions[0,0].pending.append(object());assert not predicate(None)
        main.directions[0,0].pending.clear();assert predicate(None)
        service.monitor.failure=AssertionError('foreground first mismatch')
        assert not predicate(None)
        service.monitor.failure=None
        calls.append('admission-enter');yield;calls.append('admission-exit')
    env=NS(agent=NS(training_driver=NS(admit_when=admit)),branch_path=lambda value:value,
           checker=NS(model=NS(sources=NS(main=main))))
    checks=NS(stream_pc=0x40000b10,requests=requests,program=program,arm_mixed=lambda:calls.append('armed'))
    def initialize(self,env,checks,**kw):
        self.env,self.agent,self.checks=env,env.agent,checks
        self.monitor=NS(raise_failure=lambda:None)
    monkeypatch.setattr(DirectionService,'__init__',initialize)
    service=ConfidenceBoundaryService(env,checks)
    async def query(pc):assert pc==checks.stream_pc;calls.append('genuine-loop')
    async def submit(values):
        assert values==tuple(zip(requests[3:],program.late_outcomes,strict=True))
        calls.append('one-asynchronous-submission')
    service.query=query;service.submit=submit
    await service.submit_mixed_learning()
    assert calls==['genuine-loop','armed','admission-enter','one-asynchronous-submission','admission-exit']
