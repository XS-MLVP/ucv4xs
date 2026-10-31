"""Bounded mixed-write forwarding expectations, independent of the encoder.

Both genuine prediction snapshots precede feedback. The later cold taken
branch forces SRAM rereads (Tage.scala t0_needRead), so separated feedback
uses current table state rather than trusting captured counter metadata.
Adjacent reads precede the first write: both ports request the same decrement,
and the buffer must update its resident counter twice with saturation.
This is a highest-table, zero-history scenario, not a full FTQ/allocator model.
"""
from suites.frontend.bpu.models.configuration import *
from copy import deepcopy

from suites.frontend.bpu.tage.model.mixed import expected_tage_mixed_writes


def expected_tage_overlapped_writes(pc, position, way, counter, *, mode):
    if counter not in (1, 2):
        raise ValueError('overlap scenario needs a prepared NT counter of 1 or 2')
    if mode not in ('adjacent', 'separated'):
        raise ValueError('overlap mode must be adjacent or separated')
    frames = []
    for step, newcomer in enumerate(((2 * TAGE_TABLES + 1), (2 * TAGE_TABLES + 2))):
        read_counter = counter if mode == 'adjacent' else max(0, counter-step)
        expected = expected_tage_mixed_writes(pc, position, way, read_counter)
        expected['banks'][pc & 3][1-way]['tag'] = ((pc >> 11) & 8191) ^ newcomer
        frames.append(expected['banks'])
    return {'beats': 2, 'banks': tuple(frames), 'latency_ticks': (8, 8)}


def expected_tage_overlapped_states(prepared, target, victim, way):
    """Freeze the requested final state before any checked feedback."""
    if way not in (0, 1) or target == victim or target not in prepared or victim not in prepared:
        raise ValueError('overlap states need two distinct prepared highest-table residents')
    if prepared[target]['meta']['providerTakenCtr_value'] not in (1, 2):
        raise ValueError('overlap target must start with counter 1/2')
    target_meta, victim_meta = prepared[target]['meta'], prepared[victim]['meta']
    if (target_meta['providerTableIdx'], target_meta['providerWayIdx'], target_meta['providerUsefulCtr_value']) != (TAGE_TABLES - 1,way,3):
        raise ValueError('overlap target must be protected in the requested highest-table way')
    if (victim_meta['providerTableIdx'], victim_meta['providerWayIdx'], victim_meta['providerUsefulCtr_value']) != (TAGE_TABLES - 1,1-way,0):
        raise ValueError('overlap victim must be unprotected in the other highest-table way')
    states = deepcopy(prepared)
    states[target]['meta']['providerTakenCtr_value'] = 0
    states[victim] = states[(2 * TAGE_TABLES + 1)] = None
    states[(2 * TAGE_TABLES + 2)] = {'valid': 1, 'taken': 1, 'provider_counter_valid': 1, 'meta': {
        'hasProvider': 1, 'hasAlt': 0, 'providerTableIdx': TAGE_TABLES - 1, 'providerWayIdx': 1-way,
        'providerTakenCtr_value': 4, 'providerUsefulCtr_value': 0,
        'useProvider': 1, 'altConf': 0, 'altOrBasePred': 0,
    }}
    return states
