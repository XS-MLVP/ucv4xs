"""Four distinct real history owners at one indirect PC, not a bank/set matrix."""
from suites.frontend.bpu.ittage.model.semantic import Entry

PC=0x40000800
POSITION=4
PATHS=(None,PC+2,PC+4,PC+6)
TARGETS=tuple(((((PC*2>>20)+region)<<20)|(0x2000+index*0x100))//2
    for index,region in enumerate((-1,1,2,3)))
STREAM_PC=PC+0x300
# Entry valid + tag + confidence + useful + pruned 20-bit region offset +
# four-bit region identity + PC-region selection + one padding bit, pinned
# MinimalConfig. Padding is DontCare in the semantic RTL: it occupies a mask
# bit, but must not become an independently invented functional requirement.
ENTRY_WIDTH=1+7+2+1+19+4+1+1


def payload(row,entry,*,confidence=None):
    return dict(row=row,valid=int(entry.valid),tag=entry.tag,
        confidence=entry.confidence if confidence is None else confidence,useful=entry.useful,
        offset=entry.target.offset//2,pointer=entry.target.pointer or 0,
        pc_region=int(entry.target.pointer is None),mask=(1<<ENTRY_WIDTH)-1)


def pending_plan(model,table,bank):
    return tuple(payload(slot.index,slot.patch.apply(Entry())) for slot in model.caches[table][bank].slots
        if slot is not None and slot.dirty)


def offered_payload(complete):
    """Only the actual offered fields; valid=true is constant-folded upstream.

    The complete valid bit is still checked at the SRAM-service output. This
    projection never manufactures a missing incoming signal or seeds a model.
    """
    return {name:value for name,value in complete.items() if name!='valid'}
