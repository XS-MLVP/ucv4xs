"""Conditional-outcome history, not CommonHR cells, pointers or port equations.

Final prediction completes a fetch block; a backend recovery completes ONLY
the prefix ending at its corrected instruction. Later predicted conditionals
are not executed outcomes and must not be pre-appended as not-taken.
Addresses use the integrated API's halfwords. Lookup-window/IMLI scheduling
are separate contracts, not silently claimed by this direction-history core.
"""
from dataclasses import dataclass
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.path_history import address

GHR_WIDTH,BW_WIDTH,TARGET_WIDTH=8,4,20
LOOKUP_WINDOW_CAPACITY=8 # Pinned CommonHRParameters.HistQueueSize, not a settling delay.


@dataclass(frozen=True,slots=True)
class Value:
    valid:bool=False
    ghr:int=0
    bw:int=0

    def __post_init__(self):
        if type(self.valid) is not bool or type(self.ghr) is not int or type(self.bw) is not int:
            raise ValueError('history requires semantic bool/integer values')
        if not 0<=self.ghr<1<<GHR_WIDTH or not 0<=self.bw<1<<BW_WIDTH:raise ValueError('history value out of range')

    def mapping(self):return dict(valid=int(self.valid),ghr=self.ghr,bw=self.bw)

    def append(self,bits,*,valid):
        ghr,bw=self.ghr,self.bw
        for taken,backward in bits:
            if type(taken) is not bool or type(backward) is not bool or backward and not taken:
                raise ValueError('backward outcome requires a taken conditional')
            ghr=(2*ghr+int(taken))%(1<<GHR_WIDTH)
            bw=(2*bw+int(backward))%(1<<BW_WIDTH)
        return Value(valid,ghr,bw)


@dataclass(frozen=True,slots=True)
class Block:
    pc:int
    conditionals:tuple[int,...]=()

    def __post_init__(self):
        address(self.pc)
        if type(self.conditionals) is not tuple or any(type(p) is not int or not 0<=p<16 for p in self.conditionals):
            raise ValueError('conditional positions must be immutable logical positions')
        object.__setattr__(self,'conditionals',tuple(sorted(set(self.conditionals))))

    @classmethod
    def from_token(cls,token):
        values={} if token.lookup is None else token.lookup.values()
        return cls(token.pc,tuple(values[f'{slot}.position'] for slot in range(4)
            if values.get(f'{slot}.valid') and values[f'{slot}.kind']==Kind.CONDITIONAL))

    def outcomes(self,branch,*,recovering=False):
        if not branch.taken and not recovering:return tuple((False,False) for _ in self.conditionals)
        prefix=tuple((False,False) for p in self.conditionals if p<branch.position)
        if branch.kind==Kind.CONDITIONAL:
            cfi_pc=(self.pc//8)*8+branch.position
            backward=branch.taken and cfi_pc%(1<<TARGET_WIDTH)>branch.target%(1<<TARGET_WIDTH)
            return (*prefix,(bool(branch.taken),bool(backward)))
        if not branch.taken:raise ValueError('nonconditional recovery cannot be not-taken')
        return prefix


@dataclass(frozen=True,slots=True)
class Checkpoint:
    owner:object
    value:Value
    block:Block
    serial:int


class CommonDirectionReference:
    def __init__(self):self.serial=0;self.reset()

    def reset(self):
        self.value=Value();self.pending=None;self.owned={};self.finalized=self.recoveries=0

    def checkpoint(self,owner,block,*,value=None):
        if type(block) is not Block:raise TypeError('history checkpoint requires a logical Block')
        if value is not None and type(value) is not Value:raise TypeError('lookup history must be an independently derived Value')
        checkpoint=Checkpoint(owner,self.value if value is None else value,block,self.serial)
        self.serial+=1;self.owned[checkpoint.serial]=checkpoint;return checkpoint

    def require(self,checkpoint):
        if type(checkpoint) is not Checkpoint or self.owned.get(checkpoint.serial) is not checkpoint:
            raise ValueError('history restore needs an exact owned checkpoint in this reset epoch')
        return checkpoint

    def retire(self,checkpoint):
        self.require(checkpoint)
        if self.pending is not None and self.pending[0] is checkpoint:raise ValueError('cannot retire a pending recovery owner')
        del self.owned[checkpoint.serial]

    def advance(self,*,completed=None,redirect=None,reset=False):
        if reset:self.reset();return
        if redirect is not None:self.require(redirect[0])
        if self.pending is not None:
            source,branch=self.pending
            self.require(source)
            self.value=source.value.append(source.block.outcomes(branch,recovering=True),valid=False)
            self.recoveries+=1
        elif completed is not None:
            block,branch=completed
            self.value=self.value.append(block.outcomes(branch),valid=True);self.finalized+=1
        self.pending=redirect
