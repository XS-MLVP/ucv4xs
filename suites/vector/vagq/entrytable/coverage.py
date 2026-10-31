"""Behavior-level EntryTable coverage."""
from toffee import Bin, CoverGroupDef, CoverPointDef

from .model import State


class Coverage:
    def __init__(self):
        self.group = CoverGroupDef('vagq_entrytable_contract_v1', (
            CoverPointDef('enqueue_kind', {name: Bin.values(name) for name in (
                'none', 'address_only', 'data_only', 'addr_and_data')}),
            CoverPointDef('entry_state', {name: Bin.values(name) for name in (
                'empty', 'waitA', 'waitSI', 'split', 'merge', 'wb')}),
            CoverPointDef('acceptance', {name: Bin.values(name) for name in (
                'addr_ready', 'data_ready', 'backpressure', 'redirect_flush')}),
            CoverPointDef('metadata', {
                'zero_defaults': Bin.values('zero_defaults'),
                'nonzero_core': Bin.values('nonzero_core'),
            }),
            CoverPointDef('updates', {name: Bin.values(name) for name in (
                'none', 'bitmap', 'data_sent', 'state', 'rob_clear', 'exception')}),
            CoverPointDef('priority', {name: Bin.values(name) for name in (
                'hold', 'enqueue', 'flush')}),
            CoverPointDef('age_relation', {name: Bin.values(name) for name in (
                'none', 'same_rob', 'different_rob')}),
        )).instantiate('vagq.entrytable.checked', contract='entry lifecycle and update priority/v1')

    def sample(self, state: State, beat):
        addr = any(beat.addr_valid); data = any(beat.data_valid) or any(beat.index_valid)
        if addr and data: enqueue = 'addr_and_data'
        elif addr: enqueue = 'address_only'
        elif data: enqueue = 'data_only'
        else: enqueue = 'none'
        active = next((entry for entry in state.entries if entry.valid), None)
        state_name = {0: 'empty', 1: 'waitA', 2: 'waitSI', 3: 'split', 4: 'merge', 5: 'wb'}.get(
            active.state if active else 0, 'empty')
        if beat.redirect.valid: acceptance = 'redirect_flush'
        elif addr and state.ready(beat)[0][0]: acceptance = 'addr_ready'
        elif data and state.ready(beat)[1][0]: acceptance = 'data_ready'
        elif addr or data: acceptance = 'backpressure'
        else: acceptance = 'addr_ready'
        if any(resp.entry_oh and resp.exception for resp in beat.merge_resp): update = 'exception'
        elif beat.store_update[0].valid: update = 'data_sent'
        elif beat.split_req[0].valid or any(resp.entry_oh for resp in beat.merge_resp): update = 'bitmap'
        elif beat.excp_update.valid: update = 'exception'
        elif beat.split_done.valid or beat.merge_done.valid: update = 'state'
        elif beat.rob_clear.valid: update = 'rob_clear'
        else: update = 'none'
        priority = 'flush' if beat.redirect.valid else 'enqueue' if addr or data else 'hold'
        valid_entries = [entry for entry in state.entries if entry.valid]
        robs = {(entry.rob_flag, entry.rob_value) for entry in valid_entries}
        age = 'same_rob' if len(valid_entries) >= 2 and len(robs) < len(valid_entries) else (
            'different_rob' if len(valid_entries) >= 2 else 'none'
        )
        metadata = 'nonzero_core' if any(
            packet is not None and valid and any((
                packet.meta_ftq_flag, packet.meta_ftq_value, packet.meta_ftq_offset,
                packet.meta_lq_flag, packet.meta_lq_value, packet.meta_sq_first_flag,
                packet.meta_sq_second_flag, packet.meta_sq_value, packet.meta_vsew,
                packet.meta_vlmul,
            ))
            for packet, valid in zip(beat.addr, beat.addr_valid)
        ) else 'zero_defaults'
        self.group.sample({'enqueue_kind': enqueue, 'entry_state': state_name, 'acceptance': acceptance,
                           'metadata': metadata, 'updates': update, 'priority': priority,
                           'age_relation': age})
