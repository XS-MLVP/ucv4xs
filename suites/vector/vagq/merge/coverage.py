"""Behavior coverage for MergeCtrl response and merge lifecycle."""
from toffee import Bin, CoverGroupDef, CoverPointDef

from .model import entry_alive


class Coverage:
    def __init__(self):
        self.group = CoverGroupDef('vagq_merge_contract_v1', (
            CoverPointDef('response_source', {name: Bin.values(name) for name in (
                'none', 'ldu', 'sta', 'empty', 'multi_source')}),
            CoverPointDef('response_kind', {name: Bin.values(name) for name in (
                'ack', 'NACK-clear', 'exception', 'stale/redirect miss')}),
            CoverPointDef('split_done', {name: Bin.values(name) for name in (
                'none', 'load-to-merge', 'store-to-wb', 'skip-to-wb')}),
            CoverPointDef('merge_candidate', {name: Bin.values(name) for name in (
                'none', 'no-old-vd', 'old-vd-ready', 'old-vd-blocked', 'oldest-choice')}),
            CoverPointDef('read_write_phase', {name: Bin.values(name) for name in (
                'idle', 'read-request', 'read-pending', 'write-valid', 'cancelled')}),
            CoverPointDef('mask_shape', {name: Bin.values(name) for name in (
                'full overwrite', 'partial preserve', 'agnostic fill', 'no-read zero base')}),
            CoverPointDef('rob_lifecycle', {name: Bin.values(name) for name in (
                'none', 'writeback-normal', 'writeback-exception', 'wakeup', 'clear')}),
            CoverPointDef('redirect_reuse', {name: Bin.values(name) for name in (
                'none', 'read flush', 'write flush', 'ROB reuse')}),
        )).instantiate('vagq.merge.checked', contract='response/merge/writeback lifecycle/v1')

    def sample(self, state, beat):
        responses = beat.ldu_resp + beat.sta_resp + beat.empty_resp
        valid_responses = [response for response in responses if response.valid]
        if not valid_responses:
            source = 'none'
        elif len(valid_responses) > 1:
            source = 'multi_source'
        elif responses.index(valid_responses[0]) < 3:
            source = 'ldu'
        elif responses.index(valid_responses[0]) < 5:
            source = 'sta'
        else:
            source = 'empty'
        if not valid_responses:
            response_kind = 'ack'
        elif any(response.exception for response in valid_responses):
            response_kind = 'exception'
        elif any(response.is_nack for response in valid_responses):
            response_kind = 'NACK-clear'
        elif any(
            response.entry_idx >= len(beat.entries)
            or not entry_alive(beat.entries[response.entry_idx], beat.redirect)
            for response in valid_responses
        ):
            response_kind = 'stale/redirect miss'
        else:
            response_kind = 'ack'

        split_index = state.split_done_index(beat)
        if split_index is None:
            split_kind = 'none'
        else:
            entry = beat.entries[split_index]
            split_kind = 'store-to-wb' if entry.is_store else (
                'skip-to-wb' if entry.skip_merge or not entry.merge_write else 'load-to-merge'
            )

        merge_index = state.merge_index(beat)
        if merge_index is None:
            merge_kind = 'none'
        elif sum(state.merge_candidates(beat)) > 1 and all(
            beat.psrc2_ready[index] or not state.merge_needs_old(entry)
            for index, entry in enumerate(beat.entries)
            if state.merge_candidates(beat)[index]
        ):
            merge_kind = 'oldest-choice'
        elif not state.merge_needs_old(beat.entries[merge_index]):
            merge_kind = 'no-old-vd'
        elif beat.psrc2_ready[merge_index]:
            merge_kind = 'old-vd-ready'
        else:
            merge_kind = 'old-vd-blocked'
        if merge_index is None and any(
            entry_alive(entry, beat.redirect)
            and entry.state == 4
            and state.merge_needs_old(entry)
            and not beat.psrc2_ready[index]
            for index, entry in enumerate(beat.entries)
        ):
            merge_kind = 'old-vd-blocked'

        if state.merge_resp_valid and state.pending_alive(beat):
            phase = 'write-valid'
        elif state.merge_read_valid and not state.pending_alive(beat):
            phase = 'cancelled'
        elif state.merge_read_valid:
            phase = 'read-pending'
        elif state.merge_index(beat) is not None:
            phase = 'read-request' if state.merge_needs_old(beat.entries[state.merge_index(beat)]) else 'idle'
        else:
            phase = 'idle'

        if phase == 'write-valid':
            entry = beat.entries[state.merge_pending_entry_idx]
            mask = state.merge_pending_write_mask
            agnostic = state.merge_pending_agnostic_mask
            if agnostic:
                shape = 'agnostic fill'
            elif mask == 0xffff:
                shape = 'full overwrite'
            else:
                shape = 'partial preserve'
        elif merge_index is not None and not state.merge_needs_old(beat.entries[merge_index]):
            shape = (
                'full overwrite' if beat.entries[merge_index].merge_write == 0xffff
                else 'no-read zero base'
            )
        else:
            shape = 'partial preserve'

        wb = state.observe(beat).rob_writeback
        if not wb.valid:
            lifecycle = 'clear' if state.observe(beat).rob_clear.valid else 'none'
        elif state.observe(beat).rob_clear.valid and beat.entries[wb.entry_idx].skip_merge:
            lifecycle = 'clear'
        elif wb.exception:
            lifecycle = 'writeback-exception'
        elif state.observe(beat).vp_wakeup_valid:
            lifecycle = 'wakeup'
        else:
            lifecycle = 'writeback-normal'

        if state.merge_read_valid and not state.pending_alive(beat):
            redirect = 'read flush'
        elif state.merge_resp_valid and not state.pending_alive(beat):
            redirect = 'write flush'
        elif beat.redirect.valid and any(
            entry.valid and entry.rob_value != 0 and not entry_alive(entry, beat.redirect)
            for entry in beat.entries
        ):
            redirect = 'ROB reuse'
        else:
            redirect = 'none'
        self.group.sample({
            'response_source': source,
            'response_kind': response_kind,
            'split_done': split_kind,
            'merge_candidate': merge_kind,
            'read_write_phase': phase,
            'mask_shape': shape,
            'rob_lifecycle': lifecycle,
            'redirect_reuse': redirect,
        })
