"""Checked TileLink transactions for the legacy synchronous DCache adapter.

This is not a replacement for Toffee Driver/Monitor lifecycle management. It
fixes the existing Step-based transport and records only this service window.
All handshakes are captured before the edge, never from post-edge ready values.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Acquire:
    channel: int
    opcode: int
    param: int
    size: int
    source: int
    address: int

    def legacy(self):
        return dict(channel=self.channel,opcode=self.opcode,param=self.param,
                    size=self.size,source=self.source,addr=self.address,address=self.address)


@dataclass(frozen=True)
class GrantBeat:
    index: int
    cycle: int                 # relative to this service call, not a global tick
    opcode: int
    source: int
    data: int
    denied: bool
    corrupt: bool


@dataclass(frozen=True)
class CBeat:
    channel: int
    opcode: int
    param: int
    size: int
    source: int
    address: int
    data: int

    @property
    def header(self):
        return (self.channel,self.opcode,self.param,self.size,self.source,self.address)


@dataclass(frozen=True)
class CMessage:
    header: CBeat
    data: tuple[int,...]

    @property
    def line(self):
        return sum(beat<<(256*index) for index,beat in enumerate(self.data))


class CAssembler:
    """Preserve accepted C beats, including two equal-valued data beats."""
    def __init__(self):
        self.pending={}
        self.messages=[]

    def accept(self,beat):
        if beat.opcode not in (4,5,6,7) or beat.size!=6:
            raise AssertionError(f'unsupported C message: {beat}')
        first,data=self.pending.get(beat.channel,(beat,[]))
        if first.header!=beat.header:
            raise AssertionError(f'C header changed mid-message: {first} -> {beat}')
        data=[*data,beat.data]
        count=2 if beat.opcode in (5,7) else 1  # 64B line, 32B physical beat
        if len(data)==count:
            self.messages.append(CMessage(first,tuple(data) if count==2 else ()))
            self.pending.pop(beat.channel,None)
        else:
            self.pending[beat.channel]=(first,data)

    def finish(self):
        if self.pending:
            raise AssertionError(f'incomplete C message: {self.pending}')
        return tuple(self.messages)


def check_release_data(message,*,address,line):
    """Compare all 64 bytes with the caller-owned store/memory expectation."""
    assert message.header.opcode==7, ('expected ReleaseData',message)
    assert message.header.address==address, ('release address mismatch',message,address)
    assert len(message.data)==2, ('incomplete release data',message)
    assert message.line==line, ('release data mismatch',message,line)


@dataclass(frozen=True)
class RefillResult:
    acquire: Acquire
    grants: tuple[GrantBeat,...]
    releases: tuple[CMessage,...]


class LegacyL2Responder:
    """One accepted A request, bounded D beats, optional simultaneous C capture."""
    def __init__(self,channels,step,refresh):
        if len(channels)!=2 or any(int(ch['d_data'].mWidth)!=256
                                 or int(ch['c_data'].mWidth)!=256 for ch in channels):
            raise ValueError('DCache responder requires two 256-bit TileLink channels')
        self.channels=channels
        self.step=step
        self.refresh=refresh
        self.cycle=0
        self.c=CAssembler()

    @staticmethod
    def read(signal):
        return int(signal.value)

    def edge(self,capture_c):
        self.refresh()
        if capture_c:
            for index,ch in enumerate(self.channels):
                if self.read(ch['c_valid']) and self.read(ch['c_ready']):
                    self.c.accept(CBeat(index,*(self.read(ch['c_'+name]) for name in
                        ('opcode','param','size','source','address','data'))))
        self.step(1)
        self.cycle+=1
        self.refresh()

    def run(self,expected_addr,beats,*,denied=False,corrupt=False,
            capture_c=False,grant_data=True,limit=32,drain_cycles=16):
        if len(beats)!=2 or any(not isinstance(b,int) or not 0<=b<(1<<256) for b in beats):
            raise ValueError('refill requires exactly two unsigned 256-bit data beats')
        if limit<1 or drain_cycles<0:
            raise ValueError('invalid refill service budget')
        if not grant_data and corrupt:
            raise ValueError('a no-data Grant cannot carry corrupt data')
        if any(self.read(ch['d_valid']) for ch in self.channels):
            raise RuntimeError('cannot start refill while another D offer is active')
        prior_c=[self.read(ch['c_ready']) for ch in self.channels]
        grants=[]
        for ch in self.channels:
            ch['a_ready'].Set(0)
            if capture_c:
                ch['c_ready'].Set(1)
        try:
            acquire=None
            for _ in range(limit):
                self.refresh()
                for index,ch in enumerate(self.channels):
                    if self.read(ch['a_valid']):
                        acquire=Acquire(index,*(self.read(ch['a_'+name]) for name in
                            ('opcode','param','size','source','address')))
                        break
                if acquire is not None:
                    break
                self.edge(capture_c)
            if acquire is None:
                raise AssertionError('no Acquire observed')
            if acquire.opcode not in (6,7) or acquire.size!=6 or acquire.address&63:
                raise AssertionError(f'not a cache-line Acquire: {acquire}')
            if expected_addr is not None and acquire.address!=expected_addr:
                raise AssertionError(f'Acquire address {acquire.address:#x} != {expected_addr:#x}')
            if not grant_data and acquire.opcode!=7:
                raise ValueError('no-data Grant requires a full-overwrite AcquirePerm')
            ch=self.channels[acquire.channel]
            ch['a_ready'].Set(1)  # all other A ports stay closed: no unrecorded fire
            self.refresh()
            if not self.read(ch['a_valid']) or not self.read(ch['a_ready']):
                raise AssertionError('Acquire disappeared before its acceptance edge')
            self.edge(capture_c)
            ch['a_ready'].Set(0)
            # The A handshake has completed. D may start no earlier than here.
            data=beats if grant_data else (0,)
            opcode=5 if grant_data else 4
            # Rocket TL Monitor: GrantData.denied implies corrupt. Grant has no data.
            actual_corrupt=bool(corrupt or denied) if grant_data else False
            for index,word in enumerate(data):
                fields=dict(valid=1,opcode=opcode,size=6,source=acquire.source,
                            sink=0,denied=int(denied),corrupt=int(actual_corrupt),data=word)
                for field,value in fields.items():
                    ch['d_'+field].Set(value)
                for _ in range(limit):
                    self.refresh()
                    ready=bool(self.read(ch['d_ready']))
                    accepted_cycle=self.cycle
                    self.edge(capture_c)
                    if ready:
                        grants.append(GrantBeat(index,accepted_cycle,opcode,acquire.source,
                                                word,bool(denied),actual_corrupt))
                        break
                else:
                    raise AssertionError(f'D not accepted for beat {index} within {limit} cycles')
            ch['d_valid'].Set(0)
            self.edge(capture_c)
            if capture_c:
                for _ in range(drain_cycles):
                    self.edge(True)
            return RefillResult(acquire,tuple(grants),self.c.finish())
        finally:
            for index,ch in enumerate(self.channels):
                ch['a_ready'].Set(0)
                for field in ('valid','opcode','size','source','sink','denied','corrupt','data'):
                    ch['d_'+field].Set(0)
                if capture_c:
                    ch['c_ready'].Set(prior_c[index])
            self.refresh()
