"""Completion-path injections, not native RTL functional credit."""
import pytest

from suites.memblock.mmu.l2.ptw_walker import PtwEnv, WalkRequest

pytestmark=pytest.mark.selftest


class Signal:
    def __init__(self,value=0):
        self.value=value

    def Set(self,value):
        self.value=value


def silent_environment(*,active=True):
    env=object.__new__(PtwEnv)
    env.req={'ready':Signal(1)}
    env.resp={'valid':Signal(), 'ready':Signal(),'pteidx':[Signal() for _ in range(8)]}
    env.hresp={}
    env.tick=4
    env.requests=[]
    env.llptw_requests=[dict(vpn=0x12345,source=1,s2xlate=0)]
    env._active_request=WalkRequest(2,0x12345,3,0,4,1) if active else None
    env.walk_completions=[]

    async def service(_):
        env.tick+=1

    env.service=service
    return env


async def test_old_handoff_cannot_complete_a_new_walk():
    env=silent_environment()
    with pytest.raises(TimeoutError,match='no PTW response'):
        await env.wait_response(max_cycles=2)
    assert env.walk_completions==[]


async def test_wait_without_accepted_request_is_not_a_successful_handoff():
    env=silent_environment(active=False)
    with pytest.raises(RuntimeError,match='no accepted PTW request'):
        await env.wait_response(max_cycles=2)


async def test_matching_current_handoff_is_completed_once():
    env=silent_environment()
    env.llptw_requests.append(dict(vpn=0x12345,source=3,s2xlate=0))
    assert await env.wait_response(max_cycles=2) is None
    assert [(c.request.sequence,c.kind) for c in env.walk_completions]==[(2,'llptw')]
    with pytest.raises(RuntimeError,match='no accepted PTW request'):
        await env.wait_response(max_cycles=2)


async def test_current_handoff_with_wrong_identity_is_rejected():
    env=silent_environment()
    env.llptw_requests.append(dict(vpn=0x12345,source=1,s2xlate=0))
    with pytest.raises(AssertionError,match='handoff identity mismatch'):
        await env.wait_response(max_cycles=2)
    assert env.walk_completions==[]


async def test_duplicate_current_handoff_is_not_deduplicated():
    env=silent_environment()
    env.llptw_requests.extend([dict(vpn=0x12345,source=3,s2xlate=0)]*2)
    with pytest.raises(AssertionError,match='duplicate PTW handoff'):
        await env.wait_response(max_cycles=2)


async def test_wrong_response_source_cannot_complete_the_request():
    env=silent_environment()
    env.resp.update(valid=Signal(1),source=Signal(1),s2xlate=Signal(0))
    with pytest.raises(AssertionError,match='response identity mismatch'):
        await env.wait_response(max_cycles=2)
    assert env.walk_completions==[]


async def test_scalar_x_encoding_is_rejected_before_driving_any_field():
    env=silent_environment(active=False)
    env._offered_request=None
    keys=('vpn','s2xlate','source','l3hit','l2hit','ppn','stage1hit',
          'not_super','jmp_bitmap','bitmap_pte','bitmap_splevel','valid')
    env.req={key:Signal() for key in keys}
    for key,signal in env.req.items():
        signal.mWidth=0 if key=='l2hit' else 64
    with pytest.raises(ValueError,match='l2hit does not fit 1 bits'):
        await env.issue(0x12345,l2hit=2)
    assert all(signal.value==0 for signal in env.req.values())
    assert env._offered_request is None


async def test_cancelled_request_cannot_later_complete_from_history():
    env=silent_environment()

    async def flush(_):
        env._active_request=None

    env.service=flush
    with pytest.raises(RuntimeError,match='cancelled while awaiting completion'):
        await env.wait_response(max_cycles=2)
    assert env.walk_completions==[]
