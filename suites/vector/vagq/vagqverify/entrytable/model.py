"""Independent EntryTable lifecycle model over semantic entry records."""
from dataclasses import dataclass, replace

from vagqverify.maskgen.reference import MaskRequest, evaluate_protocol

from .types import AddrPacket, Beat, DataPacket

NUM = 8
WAIT_A, WAIT_SI, SPLIT, MERGE, WB = 1, 2, 3, 4, 5
ALL = 0xffff
ENTRY_FIELDS = (
    'valid', 'meta_ftq_flag', 'meta_ftq_value', 'meta_ftq_offset', 'meta_lq_flag',
    'meta_lq_value', 'meta_sq_first_flag', 'meta_sq_second_flag', 'meta_sq_value',
    'meta_vsew', 'meta_vlmul', 'uop_type', 'rob_flag', 'rob_value', 'pdest', 'psrc2',
    'base_addr', 'op2_data',
    'ieew', 'deew', 'uop_idx', 'last_uop', 'elem_base', 'start_field', 'start_byte',
    'skip_merge', 'elem_valid', 'elem_active', 'merge_write', 'elem_agnostic', 'nf',
    'req_sent', 'req_ack', 'data_sent', 'exception', 'exception_number', 'fault_elem', 'state',
)


@dataclass(frozen=True, slots=True)
class Entry:
    valid: bool = False
    meta_ftq_flag: int = 0
    meta_ftq_value: int = 0
    meta_ftq_offset: int = 0
    meta_lq_flag: int = 0
    meta_lq_value: int = 0
    meta_sq_first_flag: int = 0
    meta_sq_second_flag: int = 0
    meta_sq_value: int = 0
    meta_vsew: int = 0
    meta_vlmul: int = 0
    uop_type: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    pdest: int = 0
    psrc2: int = 0
    base_addr: int = 0
    op2_data: int = 0
    ieew: int = 0
    deew: int = 0
    uop_idx: int = 0
    last_uop: int = 0
    elem_base: int = 0
    start_field: int = 0
    start_byte: int = 0
    skip_merge: int = 0
    elem_valid: int = 0
    elem_active: int = 0
    merge_write: int = 0
    elem_agnostic: int = 0
    nf: int = 0
    req_sent: int = 0
    req_ack: int = 0
    data_sent: int = 0
    exception: int = 0
    exception_number: int = 0
    fault_elem: int = 0
    state: int = 0

    def as_tuple(self):
        return tuple(getattr(self, field) for field in ENTRY_FIELDS)


def _flush(rob_flag, rob_value, redirect):
    if not redirect.valid:
        return False
    same = rob_flag == redirect.rob_flag and rob_value == redirect.rob_value
    return (redirect.level and same) or rob_flag != redirect.rob_flag or rob_value > redirect.rob_value


def _addr_static(packet: AddrPacket):
    masks = evaluate_protocol(MaskRequest(
        packet.v0_mask, packet.deew, packet.ieew, packet.emul, packet.vl,
        packet.vstart, packet.vma, packet.vta, packet.uop_idx, packet.nf,
    ))
    return dict(
        meta_ftq_flag=packet.meta_ftq_flag, meta_ftq_value=packet.meta_ftq_value,
        meta_ftq_offset=packet.meta_ftq_offset, meta_lq_flag=packet.meta_lq_flag,
        meta_lq_value=packet.meta_lq_value, meta_sq_first_flag=packet.meta_sq_first_flag,
        meta_sq_second_flag=packet.meta_sq_second_flag, meta_sq_value=packet.meta_sq_value,
        meta_vsew=packet.meta_vsew, meta_vlmul=packet.meta_vlmul,
        uop_type=packet.uop_type, rob_flag=packet.rob_flag, rob_value=packet.rob_value,
        pdest=packet.pdest, psrc2=packet.psrc2, base_addr=packet.base_addr,
        ieew=packet.ieew, deew=packet.deew, uop_idx=packet.uop_idx,
        last_uop=packet.last_uop, elem_base=masks['elemBase'],
        start_field=masks['startFieldOffset'], start_byte=masks['startByteOffset'],
        skip_merge=masks['skipMerge'], elem_valid=masks['elemValidMask'],
        elem_active=masks['elemActiveMask'], merge_write=masks['mergeWriteMask'],
        elem_agnostic=masks['elemAgnosticMask'], nf=packet.nf,
    )


@dataclass(frozen=True, slots=True)
class State:
    entries: tuple[Entry, ...] = (Entry(),) * NUM
    older: tuple[tuple[bool, ...], ...] = tuple(
        tuple(False for _ in range(NUM)) for _ in range(NUM)
    )

    def observe(self, beat: Beat):
        addr_ready, data_ready = self.ready(beat)
        return (
            tuple(entry.as_tuple() for entry in self.entries),
            tuple(addr_ready), tuple(data_ready), self.older,
        )

    def _accept_addr(self, index, redirect):
        entry = self.entries[index]
        return (not entry.valid or entry.state == WAIT_A) and not _flush(
            entry.rob_flag, entry.rob_value, redirect
        )

    def _accept_data(self, index, redirect):
        entry = self.entries[index]
        return (not entry.valid or entry.state == WAIT_SI) and not _flush(
            entry.rob_flag, entry.rob_value, redirect
        )

    def ready(self, beat: Beat):
        return (
            tuple(self._accept_addr((p.entry_idx if p else 0), beat.redirect) for p, valid in zip(beat.addr, beat.addr_valid)),
            tuple(self._accept_data((p.entry_idx if p else 0), beat.redirect) for p, valid in zip(beat.data, beat.data_valid)),
        )

    def _fire_addr(self, lane, beat):
        packet = beat.addr[lane]
        return bool(beat.addr_valid[lane] and packet and self._accept_addr(packet.entry_idx, beat.redirect)
                    and not _flush(packet.rob_flag, packet.rob_value, beat.redirect))

    def _fire_data(self, packet, valid, beat):
        return bool(valid and packet and self._accept_data(packet.entry_idx, beat.redirect)
                    and not _flush(packet.rob_flag, packet.rob_value, beat.redirect))

    def following(self, beat: Beat):
        entries = list(self.entries)
        addr_fire = [self._fire_addr(i, beat) for i in range(2)]
        data_fire = [self._fire_data(beat.data[i], beat.data_valid[i], beat) for i in range(2)]
        index_fire = [self._fire_data(beat.index[i], beat.index_valid[i], beat) for i in range(2)]
        for index in range(NUM):
            current = entries[index]
            addr_lanes = [i for i, fire in enumerate(addr_fire) if fire and beat.addr[i].entry_idx == index]
            data_packets = [beat.data[i] for i, fire in enumerate(data_fire) if fire and beat.data[i].entry_idx == index]
            data_packets += [beat.index[i] for i, fire in enumerate(index_fire) if fire and beat.index[i].entry_idx == index]
            enqueue_addr = bool(addr_lanes)
            enqueue_data = bool(data_packets)
            next_entry = current
            if enqueue_addr:
                packet = beat.addr[addr_lanes[-1]]
                next_entry = replace(next_entry, **_addr_static(packet))
                initial = (~next_entry.elem_valid) & ALL
            else:
                initial = 0
            if enqueue_data:
                packet = data_packets[-1]
                next_entry = replace(next_entry, op2_data=packet.op2_data,
                                     rob_flag=packet.rob_flag, rob_value=packet.rob_value)
            if enqueue_addr and enqueue_data:
                next_entry = replace(next_entry, valid=True, state=SPLIT,
                                     req_sent=initial, req_ack=initial, data_sent=initial,
                                     exception=0, exception_number=0, fault_elem=0)
            elif enqueue_addr:
                state = SPLIT if current.valid and current.state == WAIT_A else WAIT_SI
                next_entry = replace(next_entry, valid=True, state=state,
                                     req_sent=initial, req_ack=initial, data_sent=initial,
                                     exception=0, exception_number=0, fault_elem=0)
            elif enqueue_data:
                state = SPLIT if current.valid and current.state == WAIT_SI else WAIT_A
                next_entry = replace(next_entry, valid=True, state=state,
                                     req_sent=initial, req_ack=initial, data_sent=initial,
                                     exception=0, exception_number=0, fault_elem=0)

            # Non-enqueue updates follow the RTL helper priority.
            if not enqueue_addr and not enqueue_data:
                split_req = [u for u in beat.split_req if u.valid and u.entry_oh & (1 << index)]
                merge = [u for u in beat.merge_resp if u.entry_oh & (1 << index)]
                if split_req:
                    next_entry = replace(next_entry, req_sent=next_entry.req_sent | self._or_attr(split_req, 'set_req_sent'))
                if merge:
                    set_ack = self._or_attr(merge, 'set_req_ack')
                    clear_sent = self._or_attr(merge, 'clear_req_sent')
                    next_entry = replace(next_entry, req_sent=(next_entry.req_sent | self._or_attr(split_req, 'set_req_sent')) & ~clear_sent,
                                         req_ack=next_entry.req_ack | set_ack)
                    faults = [u for u in merge if u.exception]
                    if faults:
                        fault = min(faults, key=lambda u: u.fault_elem_idx)
                        if not next_entry.exception or fault.fault_elem_idx < next_entry.fault_elem:
                            next_entry = replace(next_entry, exception=1, exception_number=fault.exception_number,
                                                 fault_elem=fault.fault_elem_idx)
                if beat.excp_update.valid and beat.excp_update.entry_oh & (1 << index):
                    next_entry = replace(next_entry, req_ack=next_entry.req_ack | beat.excp_update.excp_set)
                stores = [u for u in beat.store_update if u.valid and u.entry_idx == index]
                if stores:
                    next_entry = replace(next_entry, data_sent=next_entry.data_sent | self._or_attr(stores, 'set_data_sent'))
                if beat.split_done.valid and beat.split_done.entry_oh & (1 << index):
                    next_entry = replace(next_entry, state=beat.split_done.state_next)
                if beat.merge_done.valid and beat.merge_done.entry_oh & (1 << index):
                    next_entry = replace(next_entry, state=beat.merge_done.state_next)
                if beat.rob_clear.valid and beat.rob_clear.entry_oh & (1 << index):
                    next_entry = replace(next_entry, valid=False)
            if current.valid and _flush(current.rob_flag, current.rob_value, beat.redirect):
                next_entry = replace(next_entry, valid=False)
            entries[index] = next_entry
        # olderMatrix is a registered relation.  Its combinational input
        # substitutes ROB/uop metadata for address fires, but data/index fires
        # do not participate in that substitution; their new age becomes
        # visible on the following cycle.  Keep that timing distinction rather
        # than deriving the matrix from the post-edge entry tuple directly.
        age_entries = list(self.entries)
        for lane, fire in enumerate(addr_fire):
            if fire:
                packet = beat.addr[lane]
                age_entries[packet.entry_idx] = replace(
                    age_entries[packet.entry_idx],
                    rob_flag=packet.rob_flag,
                    rob_value=packet.rob_value,
                    uop_idx=packet.uop_idx,
                )
        return State(tuple(entries), self._age(tuple(age_entries)))

    @staticmethod
    def _or_attr(values, name):
        result = 0
        for value in values:
            result |= getattr(value, name)
        return result

    @staticmethod
    def _age(entries):
        matrix = [[False] * NUM for _ in range(NUM)]
        for i in range(NUM):
            for j in range(NUM):
                if i == j:
                    continue
                left, right = entries[i], entries[j]
                if left.rob_flag == right.rob_flag and left.rob_value == right.rob_value:
                    matrix[i][j] = left.uop_idx < right.uop_idx or (
                        left.uop_idx == right.uop_idx and i < j
                    )
                else:
                    # EntryTable uses ``isAfter(rightRob, leftRob)``.  ROB
                    # pointers are circular: a flag transition reverses the
                    # value comparison rather than forming a Python tuple.
                    matrix[i][j] = bool(
                        (right.rob_flag ^ left.rob_flag)
                        ^ (right.rob_value > left.rob_value)
                    )
        return tuple(tuple(row) for row in matrix)
