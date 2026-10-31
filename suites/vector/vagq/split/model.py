"""Independent SplitCtrl pending-mask and staged-request model."""
from dataclasses import dataclass

from .types import Beat, Elem, EmptyReq, Entry, ExcpUpdate, LsuReq, Observation, Redirect, Update

NUM = 8
ACTIVE_LANES = 3
EMPTY_LANES = 2
SPLIT = 3
ALL = 0xffff


def need_flush(flag, value, redirect: Redirect):
    if not redirect.valid:
        return False
    same = flag == redirect.rob_flag and value == redirect.rob_value
    # RobPtr.isAfter is a circular comparison: a wrap flag reverses the value
    # ordering.  RedirectLevel.flushItself adds the equality case separately.
    after = bool((flag ^ redirect.rob_flag) ^ (value > redirect.rob_value))
    return bool((redirect.level and same) or after)


def idx_offset(site, entry: Entry):
    if not 0 <= site < 16 or site < entry.start_byte or not 0 <= entry.start_field <= entry.nf:
        raise ValueError('selected site/field contradicts the first MOP metadata')
    if entry.nf == 6 and entry.deew == 0 and entry.ieew == 2:
        return (site - entry.start_byte) // (1 << entry.ieew)
    data_width = (entry.nf + 1) << entry.deew
    # Measure from the FIRST MOP, not byte zero of the physical flow. A
    # continuation begins start_field elements into that segment. This stream
    # equation works for narrow and wide segments, including nonzero starts.
    relative = site - entry.start_byte + (entry.start_field << entry.deew)
    if relative < 0:
        raise ValueError('selected site precedes the first MOP in the entry')
    return relative // data_width


def element(site, entry: Entry):
    data_width = (entry.nf + 1) << entry.deew
    wider = data_width > 16
    data_mask = ALL if wider else ((1 << data_width) - 1)
    last_width = ((entry.nf + 1 - entry.start_field) << entry.deew)
    if entry.start_field and site == 0:
        data_mask = ALL if last_width >= 16 else (1 << last_width) - 1
    if data_mask & 0x100:
        data_size = 4
    elif data_mask & 0x10:
        data_size = 3
    elif data_mask & 0x4:
        data_size = 2
    elif data_mask & 0x2:
        data_size = 1
    else:
        data_size = 0
    return Elem(idx_offset(site, entry), site, 1 << site, data_mask, data_size)


def _oldest(candidates, matrix):
    for i, candidate in enumerate(candidates):
        if candidate and all((not candidates[j]) or matrix[i][j] for j in range(NUM) if j != i):
            return i
    return next((i for i, candidate in enumerate(candidates) if candidate), None)


def pending(beat: Beat):
    active = [0] * NUM
    empty = [0] * NUM
    for i, entry in enumerate(beat.entries):
        can = entry.valid and entry.state == SPLIT and not need_flush(entry.rob_flag, entry.rob_value, beat.redirect)
        idle = (~(entry.req_sent | entry.req_ack)) & entry.elem_valid & ALL
        ordered_blocked = entry.is_ordered_load and bool(entry.req_sent & ~entry.req_ack & entry.elem_active & ALL)
        active[i] = idle & entry.elem_active if can and not ordered_blocked and entry.ordered_can_proceed else 0
        empty[i] = idle & (~entry.elem_active & ALL) if can and entry.ordered_can_proceed else 0
    return tuple(active), tuple(empty)


def _select_elem(entry: Entry, mask: int, *, low=True):
    if not mask:
        return Elem()
    site = (mask & -mask).bit_length() - 1 if low else mask.bit_length() - 1
    return element(site, entry)


@dataclass(frozen=True, slots=True)
class ActiveStage:
    valid: tuple[bool, bool, bool] = (False, False, False)
    entry_idx: int = 0
    entry: Entry = Entry()
    elems: tuple[Elem, Elem, Elem] = (Elem(), Elem(), Elem())


@dataclass(frozen=True, slots=True)
class EmptyStage:
    valid: tuple[bool, bool] = (False, False)
    entry_idx: int = 0
    entry: Entry = Entry()
    elems: tuple[Elem, Elem] = (Elem(), Elem())


@dataclass(frozen=True, slots=True)
class State:
    active: ActiveStage = ActiveStage()
    empty: EmptyStage = EmptyStage()

    def _stages_flush(self, beat):
        af = any(self.active.valid) and need_flush(self.active.entry.rob_flag, self.active.entry.rob_value, beat.redirect)
        ef = any(self.empty.valid) and need_flush(self.empty.entry.rob_flag, self.empty.entry.rob_value, beat.redirect)
        return af, ef

    def _candidate(self, beat):
        active_masks, empty_masks = pending(beat)
        ai = _select_entry(active_masks, beat.older_matrix)
        ei = _select_entry(empty_masks, beat.older_matrix)
        return active_masks, empty_masks, ai, ei

    def observe(self, beat: Beat):
        active_masks, empty_masks, ai, ei = self._candidate(beat)
        af, ef = self._stages_flush(beat)
        active_cancel = tuple(
            self.active.valid[lane] and self.active.entry.exception and
            self.active.entry.fault_elem < self.active.entry.elem_base + self.active.elems[lane].idx_offset
            for lane in range(ACTIVE_LANES)
        )
        lsu = tuple(
            None if (not self.active.valid[lane] or af or active_cancel[lane]) else self._lsu(self.active.entry, self.active.entry_idx, self.active.elems[lane])
            for lane in range(ACTIVE_LANES)
        )
        empty = tuple(
            None if (not self.empty.valid[lane] or ef) else self._empty(self.empty.entry, self.empty.entry_idx, self.empty.elems[lane])
            for lane in range(EMPTY_LANES)
        )
        active_can = af or all((not self.active.valid[lane]) or active_cancel[lane] or beat.lsu_ready[lane] for lane in range(ACTIVE_LANES))
        empty_can = ef or all((not self.empty.valid[lane]) or beat.empty_ready[lane] for lane in range(EMPTY_LANES))
        active_accept = ai is not None and active_can
        empty_accept = ei is not None and empty_can
        active_update = Update(active_accept, (1 << ai) if active_accept else 0, self._active_reserve(beat.entries[ai], active_masks[ai]) if active_accept else 0)
        empty_update = Update(empty_accept, (1 << ei) if empty_accept else 0, self._empty_reserve(beat.entries[ei], empty_masks[ei]) if empty_accept else 0)
        excp_set = sum(self.active.elems[lane].sent_update for lane in range(ACTIVE_LANES) if active_cancel[lane]) & ALL
        excp = ExcpUpdate(bool(any(active_cancel) and not af), (1 << self.active.entry_idx) if any(active_cancel) and not af else 0, excp_set if not af else 0)
        return Observation(lsu, empty, (active_update, empty_update), excp)

    @staticmethod
    def _active_reserve(entry, mask):
        lanes = State._active_masks(entry, mask)
        return sum(_select_elem(entry, m).sent_update for m in lanes if m)

    @staticmethod
    def _empty_reserve(entry, mask):
        low = _select_elem(entry, mask, low=True)
        high = _select_elem(entry, mask, low=False)
        return low.sent_update | high.sent_update

    @staticmethod
    def _active_masks(entry, mask):
        if entry.is_ordered_load:
            return (mask, 0, 0)
        return tuple(sum(1 << site for site in range(16) if (site % ACTIVE_LANES) == lane and (mask & (1 << site))) for lane in range(ACTIVE_LANES))

    @staticmethod
    def _build_active(entry_idx, entry, mask):
        masks = State._active_masks(entry, mask)
        return ActiveStage(tuple(bool(m) for m in masks), entry_idx, entry, tuple(_select_elem(entry, m) for m in masks))

    @staticmethod
    def _build_empty(entry_idx, entry, mask):
        low = _select_elem(entry, mask, low=True)
        high = _select_elem(entry, mask, low=False)
        valid = (bool(mask), bool(mask) and low.byte_offset != high.byte_offset)
        return EmptyStage(valid, entry_idx, entry, (low, high))

    @staticmethod
    def _lq_add(flag, value, offset):
        total = value + offset
        return (flag ^ (total // 120)) & 1, total % 120

    @staticmethod
    def _sq_add(first, second, value, offset):
        total = second * 64 + value + offset
        return (first ^ ((total // 128) & 1), (total // 64) & 1, total % 64)

    @staticmethod
    def _address(entry, elem):
        index = entry.elem_base + elem.idx_offset
        if entry.uop_type in (0, 1):
            stride = entry.op2_data & ((1 << 64) - 1)
            value = entry.base_addr + stride * index
        else:
            count = 16 >> entry.ieew
            width = 1 << entry.ieew
            selected = index % count
            index_offset = (entry.op2_data >> (selected * width * 8)) & ((1 << (width * 8)) - 1)
            value = entry.base_addr + index_offset
        if elem.idx_offset == 0:
            value += entry.start_field << entry.deew
        return value & ((1 << 64) - 1)

    @staticmethod
    def _lsu(entry, entry_idx, elem):
        lq_flag, lq_value = State._lq_add(entry.lq_flag, entry.lq_value, elem.idx_offset if entry.is_load else 0)
        sq_first, sq_second, sq_value = State._sq_add(entry.sq_first_flag, entry.sq_second_flag, entry.sq_value, 0 if entry.is_load else elem.idx_offset)
        return LsuReq(entry_idx, entry.rob_flag, entry.rob_value, int(entry.is_load), lq_flag, lq_value,
                      sq_first, sq_second, sq_value, (entry.elem_base + elem.idx_offset) & 0x7f,
                      elem.data_size, elem.data_mask, entry.ftq_flag, entry.ftq_value, entry.ftq_offset,
                      elem.byte_offset, State._address(entry, elem), entry.pdest)

    @staticmethod
    def _empty(entry, entry_idx, elem):
        lq_flag, lq_value = State._lq_add(entry.lq_flag, entry.lq_value, elem.idx_offset if entry.is_load else 0)
        sq_first, sq_second, sq_value = State._sq_add(entry.sq_first_flag, entry.sq_second_flag, entry.sq_value, 0 if entry.is_load else elem.idx_offset)
        return EmptyReq(entry_idx, entry.rob_flag, entry.rob_value, int(entry.is_load), lq_value,
                        sq_first, sq_second, sq_value, elem.sent_update)

    def following(self, beat: Beat):
        obs = self.observe(beat)
        active_masks, empty_masks, ai, ei = self._candidate(beat)
        af, ef = self._stages_flush(beat)
        active_cancel = tuple(
            self.active.valid[lane] and self.active.entry.exception and
            self.active.entry.fault_elem < self.active.entry.elem_base + self.active.elems[lane].idx_offset
            for lane in range(ACTIVE_LANES)
        )
        active_can = af or all((not self.active.valid[lane]) or active_cancel[lane] or beat.lsu_ready[lane] for lane in range(ACTIVE_LANES))
        empty_can = ef or all((not self.empty.valid[lane]) or beat.empty_ready[lane] for lane in range(EMPTY_LANES))
        if ai is not None and active_can:
            active = self._build_active(ai, beat.entries[ai], active_masks[ai])
        elif af:
            active = ActiveStage()
        else:
            active = ActiveStage(tuple(self.active.valid[lane] and not active_cancel[lane] and not beat.lsu_ready[lane] for lane in range(ACTIVE_LANES)), self.active.entry_idx, self.active.entry, self.active.elems)
        if ei is not None and empty_can:
            empty = self._build_empty(ei, beat.entries[ei], empty_masks[ei])
        elif ef:
            empty = EmptyStage()
        else:
            empty = EmptyStage(tuple(self.empty.valid[lane] and not beat.empty_ready[lane] for lane in range(EMPTY_LANES)), self.empty.entry_idx, self.empty.entry, self.empty.elems)
        return State(active, empty)


def _select_entry(masks, matrix):
    return _oldest(tuple(bool(mask) for mask in masks), matrix)
