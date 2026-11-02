"""suites.frontend.bpu.mbtb.transaction.types components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from suites.frontend.bpu.mbtb.transaction.metadata import freeze_metadata,unsigned,metadata_origin

LOOKUP_BITS,RESOLVE_BITS=50,49


def feedback_fields(value):
    for name,bits in (('target',RESOLVE_BITS),('taken',1),('position',5),
            ('branch_type',2),('ras_action',2),('mispredict',1)):
        unsigned(getattr(value,name),bits,name)


@dataclass(frozen=True, slots=True)
class MbtbLookup:
    """Raw halfword GuardedPc.addr, including its guard bit; not bytes."""
    pc: int

    def __post_init__(self):unsigned(self.pc,LOOKUP_BITS,'lookup PC')


@dataclass(frozen=True, slots=True)
class MbtbEntry:
    valid: int
    taken: int
    target: int
    position: int
    branch_type: int
    ras_action: int

    def __post_init__(self):
        for name,bits in (('valid',1),('taken',1),('target',LOOKUP_BITS),
                ('position',5),('branch_type',2),('ras_action',2)):
            unsigned(getattr(self,name),bits,'prediction '+name)


@dataclass(frozen=True, slots=True)
class MbtbPrediction:
    entries: tuple[MbtbEntry, ...]
    meta_entries: Any

    def __post_init__(self):
        if type(self.entries) not in (tuple,list) or len(self.entries)!=10 or any(type(entry) is not MbtbEntry for entry in self.entries):
            raise ValueError('MainBTB prediction requires all ten validated result slots')
        object.__setattr__(self,'entries',tuple(self.entries))
        object.__setattr__(self,'meta_entries',freeze_metadata(self.meta_entries,prediction=True))


LOOKUP_DISPOSITIONS=frozenset(('reset-cancelled','reset-filtered','initialization-filtered',
    'disabled-filtered','initialization-before-result','disabled-before-result'))


@dataclass(frozen=True, slots=True)
class MbtbLookupDisposition:
    """A checked protocol terminal, explicitly NOT a new hardware prediction.

    preview is an immutable diagnostic sample, with no lookup-source credit.
    delivery_tick is its SDK observation window; response_tick stays absent in
    the independent ledger. SDK COMPLETED means terminal delivery, not response.
    """
    uid:int
    reason:str
    epoch:int
    offer_tick:int
    terminal_tick:int
    delivery_tick:int
    preview:MbtbPrediction

    def __post_init__(self):
        for name in ('uid','epoch','offer_tick','terminal_tick','delivery_tick'):
            value=getattr(self,name)
            if type(value) is not int or value<0:
                raise ValueError('MainBTB lookup disposition requires nonnegative identity and times')
        if type(self.reason) is not str or self.reason not in LOOKUP_DISPOSITIONS or type(self.preview) is not MbtbPrediction:
            raise ValueError('MainBTB lookup disposition requires its exact reason and diagnostic prediction')
        if metadata_origin(self.preview.meta_entries) is not None:
            raise ValueError('MainBTB terminal preview cannot claim a genuine lookup metadata source')
        if not self.offer_tick<=self.terminal_tick<=self.delivery_tick:
            raise ValueError('MainBTB lookup terminal must follow offer and precede delivery')

    def receipt(self):
        return {name:getattr(self,name) for name in
            ('uid','reason','epoch','offer_tick','terminal_tick','delivery_tick')}


@dataclass(frozen=True, slots=True)
class MbtbTraining:
    pc: int
    target: int
    taken: int
    position: int
    branch_type: int
    meta_entries: Any
    ras_action: int = 0
    mispredict: int = 1

    def __post_init__(self):
        unsigned(self.pc,RESOLVE_BITS,'resolve PC');feedback_fields(self)
        object.__setattr__(self,'meta_entries',freeze_metadata(self.meta_entries))


@dataclass(frozen=True, slots=True)
class MbtbBranchFeedback:
    target: int
    taken: int
    position: int
    branch_type: int
    ras_action: int = 0
    mispredict: int = 0

    def __post_init__(self):feedback_fields(self)


@dataclass(frozen=True, slots=True)
class MbtbBatchTraining:
    """One FTQ feedback beat with multiple resolved branches."""

    pc: int
    meta_entries: Any
    branches: tuple[MbtbBranchFeedback | None, ...]

    def __post_init__(self):
        unsigned(self.pc,RESOLVE_BITS,'resolve PC')
        if type(self.branches) not in (tuple,list) or not 1<=len(self.branches)<=8 or any(
                branch is not None and type(branch) is not MbtbBranchFeedback for branch in self.branches):
            raise ValueError('MainBTB feedback requires one to eight validated lanes, including explicit empty slots')
        branches=tuple(self.branches);active=tuple(branch for branch in branches if branch is not None)
        if sum(branch.mispredict for branch in active)>1:
            raise ValueError('MainBTB feedback permits at most one misprediction')
        if len({branch.position for branch in active})!=len(active):
            raise ValueError('MainBTB feedback cannot resolve the same position twice')
        object.__setattr__(self,'branches',branches)
        object.__setattr__(self,'meta_entries',freeze_metadata(self.meta_entries))
