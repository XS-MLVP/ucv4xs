"""Two independently owned branch records: entry and direction obligations differ."""
from bpuverify.mbtb.model.semantic import Entry,Target,coordinate,tag

PC=0x40000800
PCS=(PC,PC+0x80)
PEER_WAY,TARGET_WAY,DIRECTION_PORT=2,3,4
PEER_POSITION,POSITION=1,5
STREAM_PC=PC+0x300
# Old consumers immediately return to the normally learned early self-loop;
# a cold successor would create a genuine opposite-bank service opportunity.
old_target=lambda pc:STREAM_PC
new_target=lambda pc:pc+0x600
peer_target=lambda pc:pc+0x200


def after_earlier_branch(pc):
    """A fresh fetch start excludes the earlier instruction, exposing sibling."""
    return pc+PEER_POSITION+1


def entry_payload(row,entry):
    return dict(row=row,tag=entry.tag,position=entry.position,kind=entry.kind,action=entry.action,
        # TargetCarry is an enum: Fit=0, Overflow=1, Underflow=2.
        # The independent algorithm keeps signed region motion; this is only
        # its port projection, not two's-complement encoding of that motion.
        carry={0:0,1:1,-1:2}[entry.target.region_delta],offset=entry.target.offset)


def target_effect(pc):
    return entry_payload(coordinate(pc)[2],Entry(tag(pc),POSITION,3,0,Target.encode(pc,new_target(pc))))


def reclassification_effect(pc):
    """A complete new kind/target for the earlier logical branch."""
    return entry_payload(coordinate(pc)[2],Entry(tag(pc),PEER_POSITION,3,0,Target.encode(pc,new_target(pc))))


def counter_payload(patch):
    return dict(row=patch.row,mask=sum(1<<way for way,value in enumerate(patch.values) if value is not None),
        values={str(way):value for way,value in enumerate(patch.values) if value is not None})


def observed_counter(bits):
    """Actual masked projection only, never expected state or learning input."""
    return dict(row=bits['row'],mask=bits['mask'],
        values={str(way):value for way,value in enumerate(bits['counters']) if bits['mask']&(1<<way)})


def entry_plan(main,alignment,bank):
    cache=main.entries[alignment,bank]
    return tuple(tuple(entry_payload(v.write.row,v.write.entry) for v in sorted(cache.records.values(),key=lambda v:v.rank)
        if v.write.way==way and v.sequence in cache.outstanding) for way in range(4))
