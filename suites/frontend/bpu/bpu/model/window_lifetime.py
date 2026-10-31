"""Independent logical-window eligibility, not predictor or FTQ RTL replication.

Prediction age is distinct from resolve arrival and commit order. Metadata is
an opaque original input snapshot, never a golden predictor-table initializer.
Capacity is explicit; this model owns no clock, signal, driver or simulator.
"""
from dataclasses import dataclass
from collections.abc import Mapping


UNAVAILABLE=object()


def freeze(value):
    if value is None or type(value) in (bool,int,str):return value
    if isinstance(value,Mapping):
        if not all(type(key) is str for key in value):raise TypeError('snapshot fields need string names')
        return 'mapping',tuple((key,freeze(value[key])) for key in sorted(value))
    if type(value) in (tuple,list):return 'sequence',tuple(freeze(item) for item in value)
    raise TypeError('snapshot requires plain semantic input values, not a native handle')


@dataclass(frozen=True,slots=True,eq=False)
class Window:
    epoch:int
    sequence:int
    slot:int
    pc:int


@dataclass(frozen=True,slots=True,eq=False)
class Resolve:
    source:Window
    sequence:int
    payload:object


@dataclass(frozen=True,slots=True,eq=False)
class Teaching:
    source:Window
    sequence:int
    metadata:object
    payload:object


class LifetimeError(ValueError):
    def __init__(self,reason,source,state,*,expected=None,actual=None):
        self.reason,self.source,self.state=reason,source,state
        self.expected,self.actual=expected,actual
        super().__init__(f'{reason}; original={source!r}; state={state!r}; expected={expected!r}; actual={actual!r}')


class WindowLifetimes:
    def __init__(self,capacity):
        if type(capacity) is not int or capacity<1:raise ValueError('positive logical-window capacity required')
        self.capacity,self.epoch,self.serial,self.resolve_serial,self.teach_serial=capacity,-1,0,0,0
        self.reset()

    def reset(self):
        self.epoch+=1
        self.active=[]
        self.windows,self.slots,self.metadata,self.reasons={}, {}, {}, {}
        self.resolves,self.qualified={},set()
        self.cached=None
        self.next_slot=0
        self.accepted=[]

    @property
    def accepting(self):return len(self.active)<self.capacity

    def state(self):
        return dict(epoch=self.epoch,capacity=self.capacity,accepting=self.accepting,
            active=tuple(w.sequence for w in self.active),next_slot=self.next_slot,
            metadata_owners=tuple(sorted((slot,w.sequence) for slot,w in self.slots.items())),
            metadata_ready=tuple(sorted(self.metadata)),reasons=tuple(sorted(self.reasons.items())),
            cached=None if self.cached is None else self.cached.sequence,
            accepted=tuple(t.sequence for t in self.accepted))

    def fail(self,reason,source,**values):raise LifetimeError(reason,source,self.state(),**values)

    def known(self,source):
        if type(source) is not Window:self.fail('exact original window required',source)
        if source.epoch!=self.epoch:self.fail('old reset epoch',source)
        if self.windows.get(source.sequence) is not source:self.fail('unregistered or impersonated original',source)

    def live(self,source):
        self.known(source)
        if not any(w is source for w in self.active):self.fail(self.reasons.get(source.sequence,'source no longer active'),source)

    def admit(self,pc,*,metadata=UNAVAILABLE):
        if type(pc) is not int or pc<0:raise ValueError('nonnegative logical PC required')
        snapshot=UNAVAILABLE if metadata is UNAVAILABLE else freeze(metadata)
        if not self.accepting:self.fail('full window set cannot overwrite a live source',None)
        source=Window(self.epoch,self.serial,self.next_slot,pc)
        self.serial+=1
        self.next_slot=(self.next_slot+1)%self.capacity
        previous=self.slots.get(source.slot)
        if previous is not None:
            if any(w is previous for w in self.active):raise AssertionError('capacity contract attempted live metadata overwrite')
            self.reasons[previous.sequence]='metadata position reused'
        self.windows[source.sequence]=source
        self.slots[source.slot]=source
        self.active.append(source)
        if snapshot is not UNAVAILABLE:self.metadata[source.sequence]=snapshot
        return source

    def publish_metadata(self,source,value):
        self.live(source)
        if self.slots.get(source.slot) is not source:self.fail('metadata belongs to another generation',source)
        if source.sequence in self.metadata:self.fail('original metadata already published',source)
        snapshot=freeze(value)
        self.metadata[source.sequence]=snapshot

    def redirect(self,owner):
        self.live(owner)
        discarded=tuple(w for w in self.active if w.sequence>owner.sequence)
        self.active=[w for w in self.active if w.sequence<=owner.sequence]
        for source in discarded:self.reasons[source.sequence]='flushed by an older original'
        self.next_slot=(owner.slot+1)%self.capacity
        if self.cached is not None and self.cached.source.sequence>owner.sequence:
            self.cached=None
        return discarded

    def commit(self,source):
        # This is a declared backend commit fact, NOT inferred from a BPU
        # teaching acceptance or from retiring a verification receipt.
        self.live(source)
        if self.active[0] is not source:self.fail('commit cannot pass an older live window',source)
        self.active.pop(0)
        self.reasons[source.sequence]='committed window released'

    def resolve(self,source,payload):
        # Issued instructions may resolve after flush. Recording their arrival
        # is not qualification: qualify() below must still reject that source.
        self.known(source)
        snapshot=freeze(payload)
        result=Resolve(source,self.resolve_serial,snapshot)
        self.resolve_serial+=1
        self.resolves[result.sequence]=result
        return result

    def qualify(self,resolution):
        if type(resolution) is not Resolve or self.resolves.get(resolution.sequence) is not resolution:
            self.fail('exact original resolve required',getattr(resolution,'source',None))
        source=resolution.source
        self.known(source)
        if self.reasons.get(source.sequence)=='flushed by an older original':
            self.fail('flushed by an older original',source)
        # Commit frees queue capacity; it does not clear metaQueueResolve.
        # A queued original may still qualify before that position is reused.
        if self.slots.get(source.slot) is not source:self.fail('metadata belongs to another generation',source)
        if source.sequence not in self.metadata:self.fail('original metadata not yet published',source)
        if resolution.sequence in self.qualified:self.fail('resolve already qualified once',source)
        if self.cached is not None:self.fail('previous original teaching still awaits acceptance',source)
        result=Teaching(source,self.teach_serial,self.metadata[source.sequence],resolution.payload)
        self.teach_serial+=1
        self.qualified.add(resolution.sequence)
        self.cached=result
        return result

    def accept(self,teaching,*,metadata,payload):
        if type(teaching) is not Teaching or self.cached is not teaching:
            self.fail('no exact pending teaching for this acceptance',getattr(teaching,'source',None))
        self.known(teaching.source)
        # A qualified cache owns its original metadata even after commit and
        # slot reuse. Redirect/reset may cancel it; those clear cached above.
        for field,expected,actual in (('metadata',teaching.metadata,freeze(metadata)),
                                      ('payload',teaching.payload,freeze(payload))):
            if expected!=actual:self.fail(f'original {field} changed',teaching.source,expected=expected,actual=actual)
        self.cached=None
        self.accepted.append(teaching)
        return teaching
