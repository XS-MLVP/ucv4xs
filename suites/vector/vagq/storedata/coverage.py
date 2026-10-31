"""Behavior coverage for StoreDataCtrl's two-slot store-data protocol."""
from toffee import Bin, CoverGroupDef, CoverPointDef

from .model import entry_alive, need_flush, pending_mask


class Coverage:
    def __init__(self):
        self.group = CoverGroupDef('vagq_storedata_contract_v1', (
            CoverPointDef('candidate', {name: Bin.values(name) for name in (
                'none', 'eligible', 'blocked_no_ack', 'blocked_resident',
                'blocked_ready', 'blocked_redirect')}),
            CoverPointDef('read_phase', {name: Bin.values(name) for name in (
                'idle', 'request', 'pending', 'match', 'stale_response',
                'cancel_flush')}),
            CoverPointDef('slot_occupancy', {name: Bin.values(name) for name in (
                'empty', 'one', 'both', 'reuse_done', 'reuse_no_pending')}),
            CoverPointDef('eew', {name: Bin.values(name) for name in (
                'byte', 'half', 'word', 'double')}),
            CoverPointDef('flow_shape', {name: Bin.values(name) for name in (
                'full', 'sparse', 'start_offset', 'partial_ack')}),
            CoverPointDef('downstream', {name: Bin.values(name) for name in (
                'idle', 'backpressure', 'fire', 'permission_blocked')}),
            CoverPointDef('redirect', {name: Bin.values(name) for name in (
                'none', 'candidate_flush', 'resident_flush', 'pending_flush')}),
            CoverPointDef('update', {name: Bin.values(name) for name in (
                'none', 'slot0', 'slot1', 'both')}),
        )).instantiate(
            'vagq.storedata.checked',
            contract='two-slot acknowledged store-data protocol/v1',
        )

    @staticmethod
    def _focus_entry(state, beat):
        candidate = state.candidate_index(beat)
        if candidate is not None:
            return beat.entries[candidate]
        for slot in state.slots:
            if slot.valid:
                return beat.entries[slot.entry_idx]
        return next((entry for entry in beat.entries if entry.valid), beat.entries[0])

    def sample(self, state, beat):
        candidates = state.candidate_bits(beat)
        candidate_index = state.candidate_index(beat)
        if candidate_index is not None:
            candidate_kind = 'eligible'
        elif beat.redirect.valid and any(
            entry.valid and pending_mask(entry) for entry in beat.entries
        ):
            candidate_kind = 'blocked_redirect'
        elif any(
            entry.valid and entry.is_store and entry.state == 3
            and entry.ordered_can_proceed and beat.psrc2_ready[index]
            and pending_mask(entry) and state.resident(beat)[index]
            for index, entry in enumerate(beat.entries)
        ):
            candidate_kind = 'blocked_resident'
        elif any(
            entry.valid and entry.is_store and entry.state == 3
            and entry.ordered_can_proceed and pending_mask(entry)
            and not beat.psrc2_ready[index]
            for index, entry in enumerate(beat.entries)
        ):
            candidate_kind = 'blocked_ready'
        elif any(
            entry.valid and entry.is_store and entry.state == 3
            and entry.ordered_can_proceed and beat.psrc2_ready[index]
            and not pending_mask(entry)
            for index, entry in enumerate(beat.entries)
        ):
            candidate_kind = 'blocked_no_ack'
        else:
            candidate_kind = 'none'

        response = beat.vrf_read_resp
        response_match = (
            state.read_pending and response.valid
            and response.entry_idx == state.read_pending_entry_idx
            and response.rob_flag == state.read_pending_rob_flag
            and response.rob_value == state.read_pending_rob_value
        )
        pending_alive = True
        if state.read_pending:
            entry = beat.entries[state.read_pending_entry_idx]
            pending_alive = (
                entry.valid
                and entry.rob_flag == state.read_pending_rob_flag
                and entry.rob_value == state.read_pending_rob_value
                and not need_flush(entry.rob_flag, entry.rob_value, beat.redirect)
            )
        if response_match:
            read_phase = 'match'
        elif state.read_pending and not pending_alive:
            read_phase = 'cancel_flush'
        elif state.read_pending and response.valid:
            read_phase = 'stale_response'
        elif state.read_pending:
            read_phase = 'pending'
        elif candidate_index is not None and state.free_slot(beat) is not None:
            read_phase = 'request'
        else:
            read_phase = 'idle'

        alive = [state.slot_alive(slot, beat) for slot in state.slots]
        if any(
            slot.valid and state.slot_done(slot, beat) for slot in state.slots
        ):
            occupancy = 'reuse_done'
        elif any(
            slot.valid and not state.slot_pending(slot, beat) for slot in state.slots
        ):
            occupancy = 'reuse_no_pending'
        elif sum(alive) == 2:
            occupancy = 'both'
        elif sum(alive) == 1:
            occupancy = 'one'
        else:
            occupancy = 'empty'

        focus = self._focus_entry(state, beat)
        eew = ('byte', 'half', 'word', 'double')[focus.deew]
        if focus.start_byte:
            flow_shape = 'start_offset'
        elif focus.req_ack & focus.elem_active != focus.elem_active:
            flow_shape = 'partial_ack'
        elif focus.elem_active != 0xffff:
            flow_shape = 'sparse'
        else:
            flow_shape = 'full'

        observed = state.observe(beat)
        if any(request is not None and ready for request, ready in zip(
            observed.store_data, beat.store_data_ready
        )):
            downstream = 'fire'
        elif any(request is not None for request in observed.store_data):
            downstream = 'backpressure'
        elif any(
            slot.valid and not beat.entries[slot.entry_idx].ordered_can_proceed
            for slot in state.slots
        ):
            downstream = 'permission_blocked'
        else:
            downstream = 'idle'

        resident_flush = any(
            slot.valid
            and slot.rob_flag == beat.entries[slot.entry_idx].rob_flag
            and slot.rob_value == beat.entries[slot.entry_idx].rob_value
            and need_flush(slot.rob_flag, slot.rob_value, beat.redirect)
            for slot in state.slots
        )
        pending_flush = state.read_pending and not pending_alive
        if pending_flush:
            redirect_kind = 'pending_flush'
        elif resident_flush:
            redirect_kind = 'resident_flush'
        elif beat.redirect.valid and any(
            entry.valid and pending_mask(entry) for entry in beat.entries
        ):
            redirect_kind = 'candidate_flush'
        else:
            redirect_kind = 'none'

        update_valid = tuple(update.valid for update in observed.update)
        update_kind = (
            'both' if all(update_valid)
            else 'slot0' if update_valid[0]
            else 'slot1' if update_valid[1]
            else 'none'
        )
        self.group.sample({
            'candidate': candidate_kind,
            'read_phase': read_phase,
            'slot_occupancy': occupancy,
            'eew': eew,
            'flow_shape': flow_shape,
            'downstream': downstream,
            'redirect': redirect_kind,
            'update': update_kind,
        })
