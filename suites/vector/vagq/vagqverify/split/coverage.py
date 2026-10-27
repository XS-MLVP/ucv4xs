"""Behavior bins for SplitCtrl pending and staged request semantics."""
from toffee import Bin, CoverGroupDef, CoverPointDef

from .model import State, pending


class Coverage:
    def __init__(self):
        self.group = CoverGroupDef('vagq_split_contract_v2', (
            CoverPointDef('pending_kind', {name: Bin.values(name) for name in ('none', 'active', 'empty', 'both')}),
            CoverPointDef('selection', {name: Bin.values(name) for name in ('none', 'active_oldest', 'empty_oldest', 'both_oldest')}),
            CoverPointDef('active_action', {name: Bin.values(name) for name in ('idle', 'accept', 'hold', 'fire', 'cancel', 'flush')}),
            CoverPointDef('empty_action', {name: Bin.values(name) for name in ('idle', 'accept', 'hold', 'fire', 'flush')}),
            CoverPointDef('ordered_policy', {name: Bin.values(name) for name in ('unblocked', 'active_blocked', 'ordered_single_lane')}),
            CoverPointDef('element_shape', {name: Bin.values(name) for name in ('normal', 'wide', 'segment_last_mop')}),
            CoverPointDef('source_kind', {'load': Bin.values('load'), 'store': Bin.values('store')}),
            CoverPointDef('feedback', {name: Bin.values(name) for name in ('none', 'active_update', 'empty_update', 'exception_update', 'both_updates')}),
        )).instantiate('vagq.split.checked', contract='active/empty staged split protocol/v2; continuation identified by startFieldOffset')

    def sample(self, state: State, beat):
        active, empty = pending(beat)
        has_a, has_e = any(active), any(empty)
        kind = 'both' if has_a and has_e else 'active' if has_a else 'empty' if has_e else 'none'
        _, _, ai, ei = state._candidate(beat)
        sel = 'both_oldest' if ai is not None and ei is not None else 'active_oldest' if ai is not None else 'empty_oldest' if ei is not None else 'none'
        af, ef = state._stages_flush(beat)
        active_cancel = any(
            state.active.valid[l] and state.active.entry.exception and
            state.active.entry.fault_elem < state.active.entry.elem_base + state.active.elems[l].idx_offset
            for l in range(3)
        )
        active_ready = all((not state.active.valid[l]) or active_cancel or beat.lsu_ready[l] for l in range(3))
        empty_ready = all((not state.empty.valid[l]) or beat.empty_ready[l] for l in range(2))
        active_action = 'flush' if af else 'accept' if ai is not None and (af or active_ready) else 'cancel' if active_cancel else 'fire' if any(state.active.valid[l] and beat.lsu_ready[l] for l in range(3)) else 'hold' if any(state.active.valid) else 'idle'
        empty_action = 'flush' if ef else 'accept' if ei is not None and (ef or empty_ready) else 'fire' if any(state.empty.valid[l] and beat.empty_ready[l] for l in range(2)) else 'hold' if any(state.empty.valid) else 'idle'
        entry = beat.entries[ai] if ai is not None else next((e for e in beat.entries if e.valid), beat.entries[0])
        if entry.is_ordered_load and not any(active) and bool(entry.req_sent & ~entry.req_ack & entry.elem_active):
            ordered = 'active_blocked'
        elif entry.is_ordered_load:
            ordered = 'ordered_single_lane'
        else:
            ordered = 'unblocked'
        width = (entry.nf + 1) << entry.deew
        shape = 'segment_last_mop' if entry.nf and entry.start_field else 'wide' if width > 16 else 'normal'
        observed = state.observe(beat)
        feedback = 'both_updates' if observed.update[0].valid and observed.update[1].valid else 'active_update' if observed.update[0].valid else 'empty_update' if observed.update[1].valid else 'exception_update' if observed.excp.valid else 'none'
        self.group.sample({'pending_kind': kind, 'selection': sel, 'active_action': active_action,
                           'empty_action': empty_action, 'ordered_policy': ordered,
                           'element_shape': shape, 'source_kind': 'load' if entry.is_load else 'store',
                           'feedback': feedback})
