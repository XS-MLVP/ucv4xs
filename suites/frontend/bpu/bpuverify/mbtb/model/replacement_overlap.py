"""Logical branch program for latest-age selection; no DUT inputs or snapshots.

Two SRAM rows may share replacement age. The third context is independent.
Both forward and no-forward outcomes are declared before any drive, and each
positive must distinguish the stale victim from the latest victim.
"""
from dataclasses import dataclass, replace

from bpuverify.mbtb.model.replacement import MbtbReplacementState

CASES = ('same-taken','alias-taken','independent-taken',
         'same-not-taken','alias-not-taken','independent-not-taken','lookup-only')
PC, NEW_POSITION = 0x40000880, 3


@dataclass(frozen=True, slots=True)
class Resident:
    pc: int
    position: int
    target: int
    way: int
    counter: int


class ReplacementProgram:
    def __init__(self, mode):
        if mode not in CASES: raise ValueError(f'unknown replacement program {mode}')
        self.mode=mode
        self.pcs=dict(same=PC,alias=PC^0x2000,independent=PC^0x80)
        self.lookup_only=mode=='lookup-only'
        relation='same' if self.lookup_only else mode.split('-',1)[0]
        self.taken=not self.lookup_only and not mode.endswith('not-taken')
        age=MbtbReplacementState()
        records=[]
        for pc in self.pcs.values():
            for position in (1,5,9,13):
                way=age.allocate(pc,position)
                # Learning the later branch includes the earlier NT prefix.
                records.append(Resident(pc,position,pc+0x600+position*0x10,way,
                                        1 if position!=13 else 2))
        self.prepared=tuple(records)
        self.old_victim=age.victim(PC,NEW_POSITION)
        self.touch=next(r for r in records if r.pc==self.pcs[relation] and r.way==self.old_victim)
        if not self.lookup_only:
            age.feedback(self.touch.pc,self.touch.position,self.touch.way,taken=int(self.taken))
        self.victim=age.allocate(PC,NEW_POSITION)
        self.forwarded=relation in ('same','alias') and self.taken
        assert (self.victim!=self.old_victim)==self.forwarded, 'non-discriminating replacement prestate'
        self.new=Resident(PC,NEW_POSITION,PC+0x980,self.victim,2)
        final=[]
        for record in records:
            if record.pc==PC and record.way==self.victim:continue
            counter=record.counter
            if not self.lookup_only and record==self.touch:
                counter=max(0,min(3,counter+(1 if self.taken else -1)))
            if record.pc==PC and record.position==1:
                # The allocating source was captured BEFORE the touch; its
                # direction projection uses that original counter, not SRAM.
                counter=max(0,record.counter-1)
            final.append(replace(record,counter=counter))
        # The displaced Main record remains observable in DefaultConfig's
        # VictimBTB with its independent weak-taken direction initialization.
        removed=next(r for r in records if r.pc==PC and r.way==self.victim)
        self.final=tuple(final)+(self.new,replace(removed,way=4,counter=2))
        self.removed=next(r for r in records if r.pc==PC and r.way==self.victim)

    def profile(self, pc, *, prepared=False):
        return tuple(sorted((r for r in (self.prepared if prepared else self.final) if r.pc==pc),
                            key=lambda r:r.way))

    def state(self):
        return dict(mode=self.mode,touch=self.touch,old_victim=self.old_victim,victim=self.victim,
                    forwarded=self.forwarded,prepared=self.prepared,final=self.final)
