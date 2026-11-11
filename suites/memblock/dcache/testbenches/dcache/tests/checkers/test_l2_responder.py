"""Transport injections, not DUT mutation or native functional credit."""
import pytest
from types import SimpleNamespace

from suites.memblock.dcache.testbenches.dcache.env.tilelink import CAssembler
from suites.memblock.dcache.testbenches.dcache.env.tilelink import CBeat
from suites.memblock.dcache.testbenches.dcache.env.tilelink import LegacyL2Responder
from suites.memblock.dcache.testbenches.dcache.env.tilelink import check_release_data

pytestmark=pytest.mark.selftest


class Signal:
    def __init__(self,value=0):
        self.value=value
        self.mWidth=256

    def Set(self,value):
        self.value=value


class Bus:
    def __init__(self,*,ready='high',both=False,opcode=6):
        self.channels=[]
        for index in range(2):
            fields={prefix+name:Signal() for prefix,names in (
                ('a_',('valid','ready','opcode','param','size','source','address')),
                ('c_',('valid','ready','opcode','param','size','source','address','data')),
                ('d_',('valid','ready','opcode','size','source','sink','denied','corrupt','data'))
            ) for name in names}
            for name,value in dict(valid=int(index==0 or both),opcode=opcode,size=6,
                                   source=3+index,address=0x1000+64*index).items():
                fields['a_'+name].Set(value)
            fields['d_ready'].Set(0 if ready=='rise' else 1)
            self.channels.append(fields)
        self.ready=ready
        self.acquires=[]
        self.grants=[]
        self.offers=[]
        self.stall=0

    def refresh(self):
        pass

    def step(self,cycles):
        assert cycles==1
        for index,ch in enumerate(self.channels):
            if ch['a_valid'].value and ch['a_ready'].value:
                self.acquires.append(index)
                ch['a_valid'].Set(0)
            if not ch['d_valid'].value:
                continue
            offer=tuple(ch['d_'+field].value for field in ('opcode','source','data','denied','corrupt'))
            self.offers.append((index,offer))
            if ch['d_ready'].value:
                self.grants.append((index,offer))
                if self.ready=='fall' and len(self.grants)==1:
                    ch['d_ready'].Set(0)
            elif self.ready!='never':
                self.stall+=1
                ch['d_ready'].Set(1)

    def responder(self):
        return LegacyL2Responder(self.channels,self.step,self.refresh)


def test_post_edge_ready_fall_does_not_reject_an_accepted_beat():
    bus=Bus(ready='fall')
    result=bus.responder().run(0x1000,(0x111,0x222))
    assert [record[1][2] for record in bus.grants]==[0x111,0x222]
    assert [beat.data for beat in result.grants]==[0x111,0x222]
    assert bus.stall==1


def test_post_edge_ready_rise_does_not_fake_acceptance():
    bus=Bus(ready='rise')
    result=bus.responder().run(0x1000,(0x111,0x222))
    assert [record[1][2] for record in bus.grants]==[0x111,0x222]
    assert [offer[1][2] for offer in bus.offers]==[0x111,0x111,0x222]
    assert len(result.grants)==2


def test_other_channel_is_not_accepted_without_a_recorded_response():
    bus=Bus(both=True)
    first=bus.responder().run(0x1000,(1,2))
    assert first.acquire.channel==0 and bus.acquires==[0]
    assert bus.channels[1]['a_valid'].value==1
    second=bus.responder().run(0x1040,(3,4))
    assert second.acquire.channel==1 and bus.acquires==[0,1]


def test_timeout_is_not_a_zero_beat_success_and_restores_inputs():
    bus=Bus(ready='never');bus.channels[0]['d_ready'].Set(0)
    with pytest.raises(AssertionError,match='D not accepted'):
        bus.responder().run(0x1000,(1,2),limit=2)
    assert bus.grants==[]
    assert all(ch['a_ready'].value==0 and ch['d_valid'].value==0 for ch in bus.channels)


def test_denied_grantdata_sets_corrupt_on_every_beat():
    bus=Bus()
    result=bus.responder().run(0x1000,(1,2),denied=True)
    assert all(beat.denied and beat.corrupt for beat in result.grants)
    assert all(record[1][3:]==(1,1) for record in bus.grants)


def test_full_overwrite_can_receive_one_no_data_grant():
    bus=Bus(opcode=7)
    result=bus.responder().run(0x1000,(1,2),grant_data=False)
    assert len(result.grants)==1 and result.grants[0].opcode==4
    assert len(bus.grants)==1 and bus.grants[0][1][2]==0


@pytest.mark.parametrize('beats',[(1,),(-1,2),(1,1<<256)])
def test_bad_line_payload_is_rejected_before_acceptance(beats):
    bus=Bus()
    with pytest.raises(ValueError,match='two unsigned 256-bit'):
        bus.responder().run(0x1000,beats)
    assert bus.acquires==[] and bus.grants==[]


def test_c_assembler_keeps_equal_data_beats_and_second_beat_errors_visible():
    first=CBeat(0,7,1,6,2,0x1000,0x1122)
    assembler=CAssembler()
    assembler.accept(first)
    with pytest.raises(AssertionError,match='incomplete C message'):
        assembler.finish()
    assembler.accept(first)  # Equal values are still two accepted transfers.
    message,=assembler.finish()
    assert message.data==(0x1122,0x1122)
    check_release_data(message,address=0x1000,line=0x1122+(0x1122<<256))
    with pytest.raises(AssertionError,match='release data mismatch'):
        check_release_data(message,address=0x1000,line=0x1122+(0x3344<<256))


def test_c_assembler_rejects_header_change_mid_message():
    assembler=CAssembler()
    assembler.accept(CBeat(0,7,1,6,2,0x1000,1))
    with pytest.raises(AssertionError,match='header changed'):
        assembler.accept(CBeat(0,7,1,6,2,0x1040,2))


def test_wrong_native_beat_width_is_not_silently_truncated():
    bus=Bus();bus.channels[0]['d_data'].mWidth=128
    with pytest.raises(ValueError,match='two 256-bit'):
        bus.responder()
    assert bus.acquires==[] and bus.grants==[]


def release_environment(*,ready=True):
    bus=Bus(ready='high' if ready else 'never')
    for ch in bus.channels:
        ch['a_valid'].Set(0)
    ch=bus.channels[0]
    for field,value in dict(valid=1,opcode=7,param=1,size=6,source=5,
                            address=0x1000,data=0x11).items():
        ch['c_'+field].Set(value)
    if not ready:
        ch['d_ready'].Set(0)
    accepted=[]

    def edge(cycles):
        c_fire=bool(ch['c_valid'].value and ch['c_ready'].value)
        if ch['d_valid'].value:
            assert len(accepted)==2, 'D ack offered before complete C acceptance'
        bus.step(cycles)
        if c_fire:
            accepted.append(ch['c_data'].value)
            ch['c_data'].Set(0x22)
            if len(accepted)==2:
                ch['c_valid'].Set(0)

    env=SimpleNamespace(channels=bus.channels,dut=SimpleNamespace(Step=edge),
                        refresh=bus.refresh,_val=lambda signal:int(signal.value))
    line=(0x11+(0x22<<256)).to_bytes(64,'little')
    model={'l2':{0x1000:bytearray(line)},'pending':{},'releases':{},'retired':set()}
    return env,bus,model


def test_random_l2_ack_uses_completed_c_source_not_a_constant():
    from suites.memblock.dcache.testbenches.dcache.env.traffic import ack_ready
    from suites.memblock.dcache.testbenches.dcache.env.traffic import pump
    env,bus,model=release_environment()
    ack_ready(env)
    assert not any(ch['d_valid'].value for ch in bus.channels)
    pump(env,model,1)
    assert bus.grants==[(0,(6,5,0,0,0))]
    assert len(model['releases'])==1 and not any(model['release_acks'])
    assert not any(ch['d_valid'].value or ch['c_ready'].value for ch in bus.channels)


def test_random_l2_ack_timeout_does_not_erase_an_obligation():
    from suites.memblock.dcache.testbenches.dcache.env.traffic import pump
    env,bus,model=release_environment(ready=False)
    with pytest.raises(AssertionError,match='incomplete Release/ReleaseAck'):
        pump(env,model,1)
    assert bus.grants==[] and model['release_acks'][0]==[(5,6)]


def test_refill_provider_does_not_leak_expected_store_bytes_to_the_dut():
    from suites.memblock.dcache.testbenches.dcache.env.traffic import service
    bus=Bus();offered=[]
    env=SimpleNamespace(channels=bus.channels,
                        service_miss=lambda address,**kwargs:offered.append(kwargs['data_beats']))
    model={'l2':{0x1000:bytearray(64)},'pending':{0x1000:{4:0xAA}}}
    service(env,model,0x1000,'independent L2')
    assert offered==[[0,0]]
    assert model['pending']=={0x1000:{4:0xAA}}
