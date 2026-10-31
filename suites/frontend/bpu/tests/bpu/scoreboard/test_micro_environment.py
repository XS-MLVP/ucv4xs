"""Environment hides source timing and requires compared, not just modeled, effects."""
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.bpu.env.micro import MicroProgram


@pytest.mark.parametrize('learning,actual,expected',((None,(3,),True),(object(),(3,),False),(None,(2,),False),(None,None,False)))
def test_completion_requires_a_matching_compared_projection_without_seeding(learning,actual,expected):
    micro = NS(learning=learning,entries=[NS(confidence=3)])
    checker = NS(model=NS(sources=NS(micro=micro)),micro_checked=None if actual is None else (10,actual))
    assert MicroProgram.effects_compared(checker) is expected
    assert micro.entries[0].confidence==3


@pytest.mark.parametrize('failure',(False,True))
async def test_capture_verifies_exact_source_before_quieting_again_and_never_retries(failure):
    calls,source = [],object()
    async def pause():calls.append('pause')
    async def redirect(request):
        calls.append(('redirect',request.pc))
        return 100
    async def ready(**values):calls.append(('ready',values))
    async def receive(**selection):
        calls.append(('receive',selection))
        return source
    error = AssertionError('bad owned source')
    def verify(value):
        assert value is source
        calls.append('verify')
        if failure:raise error
    agent = NS(redirect=redirect,set_ready=ready,next_transaction=receive)
    env = object.__new__(MicroProgram)
    env.agent,env.anchor,env.pc,env.pause = agent,NS(meta=NS(redirect={})),0x40000800,pause
    if failure:
        with pytest.raises(AssertionError) as caught:await env.capture(0x40000900,verify)
        assert caught.value is error and calls[-1]=='verify'
    else:
        assert await env.capture(0x40000900,verify) is source
        assert calls[-2:]==['verify','pause']
    assert calls[0]=='pause' and calls.count('verify')==1
    assert ('receive',dict(start_pc=0x40000900,after_tick=100)) in calls
