"""Driver admission owns launch timing, not request identity or acceptance."""
import asyncio

import pytest
from toffee import Bundle,ClockCycles,Execution,MemoryBackend,ReadyValid,Role

from suites.frontend.bpu.bpu.driver.training import BpuTrainingDriver


class Signal:
    def __init__(self,value=0):self.value=value


def driver(clock,calls):
    port=ReadyValid(clock=clock,valid=Signal(),ready=Signal(1),bits=Bundle(data=Signal()),
        role=Role.PRODUCER,name='training')
    def encode(bits,request):
        calls.append(request)
        bits.data.value=request['value']
    return BpuTrainingDriver(port,encoder=encode)


async def test_queued_requests_keep_identity_and_retry_only_the_current_launch():
    clock,calls,attempts=object(),[],[]
    a,b={'value':11},{'value':22}
    async with Execution(MemoryBackend(clock)):
        async with driver(clock,calls) as port:
            def admit(request):
                attempts.append(request)
                return request is b or len(attempts)==3
            with port.admit_when(admit):
                first,second=port.send(a),port.send(b)
                assert first.request is a and second.request is b
                assert ((await first).tick,(await second).tick)==(6,8)
            assert calls==[a,b] and attempts==[a,a,a,b]
            assert (await port.send({'value':33})).tick==10
            assert len(attempts)==4 and not port.has_outstanding


async def test_admission_cancellation_restores_normal_driver_without_encoding():
    clock,calls=object(),[]
    async with Execution(MemoryBackend(clock)):
        async with driver(clock,calls) as port:
            with port.admit_when(lambda _:False):
                handle=port.send({'value':11})
                await ClockCycles(clock,2)
                with pytest.raises(RuntimeError,match='idle driver'):
                    with port.admit_when(lambda _:True):pass
                handle.cancel()
                with pytest.raises(asyncio.CancelledError):await handle
                await ClockCycles(clock,1)
            assert not calls and port.interface.valid.value==0
            await port.send({'value':22})
            assert calls==[{'value':22}]


@pytest.mark.parametrize('error_type',(AssertionError,TimeoutError,ValueError))
async def test_admission_failure_reaches_transfer_as_the_original_exception(error_type):
    clock,calls,error=object(),[],error_type('original admission failure')
    def reject(_):raise error
    async with Execution(MemoryBackend(clock)):
        async with driver(clock,calls) as port:
            with port.admit_when(reject):
                with pytest.raises(error_type) as caught:await port.send({'value':11})
                assert caught.value is error
            assert not calls and not port.has_outstanding and port.interface.valid.value==0


async def test_scope_rejects_nested_or_noncallable_admission_and_restores_on_body_error():
    clock,calls=object(),[]
    async with Execution(MemoryBackend(clock)):
        async with driver(clock,calls) as port:
            with pytest.raises(TypeError,match='callable'):
                with port.admit_when(1):pass
            with pytest.raises(ValueError,match='body'):
                with port.admit_when(lambda _:False):
                    with pytest.raises(RuntimeError,match='exclusive'):
                        with port.admit_when(lambda _:True):pass
                    raise ValueError('body')
            await port.send({'value':22})
            assert calls==[{'value':22}]


@pytest.mark.parametrize('point',('before-worker','waiting','early-normal-exit'))
async def test_leaving_scope_with_unaccepted_work_cancels_it_without_later_ungated_launch(point):
    clock,calls=object(),[]
    async with Execution(MemoryBackend(clock)):
        async with driver(clock,calls) as port:
            error=ValueError('original body failure')
            expected=RuntimeError if point=='early-normal-exit' else ValueError
            with pytest.raises(expected) as caught:
                with port.admit_when(lambda _:False):
                    first,second=port.send({'value':11}),port.send({'value':12})
                    if point=='waiting':await ClockCycles(clock,2)
                    if point!='early-normal-exit':raise error
            if point!='early-normal-exit':assert caught.value is error
            assert first.done() and second.done() and not port.has_outstanding
            await ClockCycles(clock,2)
            assert not calls and port.interface.valid.value==0
            await port.send({'value':22})
            assert calls==[{'value':22}]
