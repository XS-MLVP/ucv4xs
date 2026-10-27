"""Bounded independent TAGE entry-buffer writes, including retained owners.

All requests read the same pre-cycle state. Drain runs first; a write wins
over drain in its selected slot. Two different keys may hit or miss, but
must select different slots. A collision or full-row-miss/PLRU outcome is
explicitly unsupported, not resolved by inventing a priority policy.
"""
from collections.abc import Mapping
from copy import deepcopy

from bpuverify.tage.model.shadow import advance_tage_shadow


def advance_tage_shadow_writes(banks, read_ready, frames):
    """Advance one cycle with a four-bank/two-port immutable request frame.

    Inactive ports are ``None``; active payloads have the single-write model's
    fields. The real TAGE parent selects one bank and a common set index per
    cycle. Retained owner/depth need not equal the requesting physical port.
    Inputs must be independently frozen before driving, not observed results.
    """
    if (not isinstance(frames, (tuple, list)) or len(frames) != 4
        or any(not isinstance(row, (tuple, list)) or len(row) != 2 for row in frames)):
        raise ValueError('TAGE write frame requires four banks and two ports')
    active = [(bank, port, payload) for bank, row in enumerate(frames)
              for port, payload in enumerate(row) if payload is not None]
    if len(active) > 2 or len({bank for bank, _, _ in active}) > 1:
        raise ValueError('TAGE parent can write at most two ports of one bank')
    if any(not isinstance(payload, Mapping) for _, _, payload in active):
        raise ValueError('TAGE active write payload must be a mapping')
    after = advance_tage_shadow(banks, read_ready)['banks']
    steps = [(bank, port, payload,
              advance_tage_shadow(banks, read_ready, bank=bank, port=port, write=payload))
             for bank, port, payload in active]
    if len({payload['set_idx'] for _, _, payload in active}) > 1:
        raise ValueError('TAGE parent writes a common set index per bank')
    keys = [(bank, payload['set_idx'], payload['tag']) for bank, _, payload in active]
    if len(set(keys)) != len(keys):
        raise ValueError('TAGE cannot write the same key through both ports')
    touched = [(bank, step['owner'], step['depth']) for bank, _, _, step in steps]
    if len(set(touched)) != len(touched):
        raise ValueError('colliding retained slots are outside the independent-write reference')
    transitions = []
    for bank, port, payload, step in steps:
        owner, depth = step['owner'], step['depth']
        before = banks[bank][owner][depth]
        after[bank][owner][depth].update(deepcopy(step['banks'][bank][owner][depth]))
        transitions.append(dict(bank=bank, request_port=port, owner=owner, depth=depth,
            hit=int(bool(before['valid']) and (before['set_idx'], before['tag']) ==
                    (payload['set_idx'], payload['tag'])),
            old_counter=before['counter'], request_counter=payload['counter'],
            new_counter=after[bank][owner][depth]['counter'], dirty=before['dirty'],
            ready=read_ready[bank][owner], old_valid=before['valid'],
            old_set_idx=before['set_idx'], old_tag=before['tag']))
    return dict(banks=after, writes=tuple(transitions))
