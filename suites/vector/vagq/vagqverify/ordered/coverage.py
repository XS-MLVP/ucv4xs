"""Behavior bins for permit gating, handoff, consume and ROB flush."""
from toffee import Bin, CoverGroupDef, CoverPointDef

from .model import State


def _entry_gate(state, beat):
    entry = beat.entries[0]
    if not entry.valid:
        return 'invalid'
    if not entry.is_ordered:
        return 'unordered'
    if not entry.is_load:
        return 'store'
    if entry.uop_idx == 0:
        return 'ordered_first'
    return 'ordered_permitted' if state.observe(beat.entries).ordered_can_proceed[0] else 'ordered_waiting'


class Coverage:
    def __init__(self):
        self.group = CoverGroupDef('vagq_ordered_permit_contract_v1', (
            CoverPointDef('entry_gate', {name: Bin.values(name) for name in (
                'invalid', 'unordered', 'store', 'ordered_first',
                'ordered_waiting', 'ordered_permitted')}),
            CoverPointDef('completion', {name: Bin.values(name) for name in (
                'none', 'ordered_middle', 'ordered_last', 'ordered_exception')}),
            CoverPointDef('permit_action', {name: Bin.values(name) for name in (
                'none', 'handoff', 'consume', 'consume_and_handoff')}),
            CoverPointDef('successor', {name: Bin.values(name) for name in (
                'adjacent', 'middle_adjacent', 'ring_wrap', 'target_waitA', 'not_applicable')}),
            CoverPointDef('redirect_effect', {name: Bin.values(name) for name in (
                'none', 'flush_self', 'flush_younger', 'no_match')}),
            CoverPointDef('rob_relation', {name: Bin.values(name) for name in (
                'same', 'older_preserved', 'younger_flushed', 'flag_wrap', 'not_applicable')}),
            CoverPointDef('uop_relation', {name: Bin.values(name) for name in (
                'match', 'mismatch', 'not_applicable')}),
        )).instantiate('vagq.ordered_permit.checked', contract='ordered permit state/gating/v1')

    def sample(self, state, beat):
        entry = state.selected(beat)
        ordered, consume, handoff, successor = state.actions(beat)
        if not ordered:
            completion = 'none'
            action = 'none'
            successor_bin = 'not_applicable'
        else:
            completion = 'ordered_exception' if entry.exception else 'ordered_last' if entry.last_uop else 'ordered_middle'
            action = 'consume_and_handoff' if consume and handoff else 'consume' if consume else 'handoff' if handoff else 'none'
            successor_bin = 'not_applicable'
            if handoff:
                successor_bin = 'ring_wrap' if successor == 0 else (
                    'middle_adjacent' if successor in (4, 5, 6) else 'adjacent'
                )
                if beat.entries[successor].state == 1:
                    successor_bin = 'target_waitA'
        redirect = beat.redirect
        if not redirect.valid:
            redirect_effect = 'none'
            rob_relation = 'not_applicable'
        else:
            permits = [p for p in state.permits if p is not None]
            flushed = [p for p in permits if (
                (redirect.level and p.rob_flag == redirect.rob_flag and p.rob_value == redirect.rob_value)
                or p.rob_flag != redirect.rob_flag or p.rob_value > redirect.rob_value
            )]
            same_target = any(
                p.rob_flag == redirect.rob_flag and p.rob_value == redirect.rob_value
                for p in permits
            )
            redirect_effect = 'flush_self' if redirect.level and flushed and any(
                p.rob_flag == redirect.rob_flag and p.rob_value == redirect.rob_value for p in flushed
            ) else 'flush_younger' if flushed else 'no_match'
            if any(p.rob_flag != redirect.rob_flag for p in flushed):
                rob_relation = 'flag_wrap'
            elif redirect.level and same_target:
                rob_relation = 'same'
            elif flushed:
                rob_relation = 'younger_flushed'
            elif permits:
                rob_relation = 'older_preserved'
            else:
                rob_relation = 'not_applicable'
        if entry is None or not entry.is_ordered_load or entry.uop_idx == 0:
            uop_relation = 'not_applicable'
        else:
            permit = state.permits[beat.split_done.entry_idx] if beat.split_done.valid else None
            uop_relation = 'match' if permit is not None and permit.uop_idx == entry.uop_idx else 'mismatch'
        self.group.sample({
            'entry_gate': _entry_gate(state, beat),
            'completion': completion,
            'permit_action': action,
            'successor': successor_bin,
            'redirect_effect': redirect_effect,
            'rob_relation': rob_relation,
            'uop_relation': uop_relation,
        })
