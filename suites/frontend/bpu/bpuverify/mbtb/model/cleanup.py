"""Bounded, independent MainBTB multi-hit cleanup plus retarget expectations."""
from bpuverify.common.model.configuration import *
from copy import deepcopy
from dataclasses import replace


def expected_mbtb_cleanup_states(duplicate, neighbor, pc, align, way, target):
    """Keep the lower duplicate, clear the upper and retarget another set.

    The prepared indirect residents have weak-positive counters. Cleanup does
    not initialize counters, and a same-attribute indirect retarget preserves
    them. Inputs are immutable full public profiles, not encoder output.
    """
    if align not in (0, 1) or way not in range(MAIN_WAYS):
        raise ValueError('cleanup requires a physical align bank and way')
    lower, upper = align * (MAIN_WAYS + 1), align * (MAIN_WAYS + 1) + 1
    entries = duplicate['entries']
    if len(entries) != RESULT_SLOTS or any(entry.valid for index, entry in enumerate(entries) if index not in (lower, upper)):
        raise ValueError('cleanup requires exactly two active duplicate ways')
    if not all(entries[index].valid and entries[index].branch_type == 3 for index in (lower, upper)) or entries[lower].position != entries[upper].position:
        raise ValueError('cleanup requires same-position indirect duplicates')
    if any(duplicate['meta_entries'][align][index]['counter_value'] != 2 for index in range(2)):
        raise ValueError('cleanup reference requires weak-positive duplicate counters')
    chosen = neighbor['entries'][align * (MAIN_WAYS + 1) + way]
    if not chosen.valid or chosen.branch_type != 3 or neighbor['meta_entries'][align][way]['counter_value'] != 2:
        raise ValueError('cleanup reference requires a weak-positive indirect neighbor')
    cleaned, updated = deepcopy(duplicate), deepcopy(neighbor)
    cleaned['entries'] = tuple(replace(entry, valid=0, target=pc & ~((1 << 20) - 1),
        position=align * ALIGN_HALFWORDS, branch_type=0, ras_action=0) if index == upper else entry
        for index, entry in enumerate(entries))
    cleaned['meta_entries'][align][1].update(rawHit=0, position=align * ALIGN_HALFWORDS,
        attribute=dict(branchType=0, rasAction=0))
    updated['entries'] = tuple(replace(entry, target=target) if index == align * (MAIN_WAYS + 1) + way else entry
        for index, entry in enumerate(updated['entries']))
    return cleaned, updated


def mbtb_entry_slot(vector, *, dirty=0):
    """This scenario uses Fit targets and positions within one align bank."""
    if vector.pc >> 20 != vector.target >> 20:
        raise ValueError('cleanup native reference requires a Fit target')
    return dict(valid=1, dirty=dirty, set_idx=(vector.pc >> 7) & (MAIN_ROWS - 1),
        tag=(vector.pc >> 15) & 65535, position=vector.position % ALIGN_HALFWORDS,
        branch_type=vector.branch_type, ras_action=0, carry=0,
        lower=vector.target & ((1 << 20) - 1))


def expected_mbtb_cleanup_dual(original, changed, extra, updated, depth, shadow_state):
    """Predict both complete write payloads and all four pre/post shadow slots."""
    if depth not in (0, 1) or shadow_state not in ('dirty', 'clean'):
        raise ValueError('cleanup native reference requires depth zero/one and dirty/clean')
    empty = dict(valid=0, dirty=0, set_idx=0, tag=0, position=0,
                 branch_type=0, ras_action=0, carry=0, lower=0)
    clear = dict(empty, valid=1, set_idx=(original.pc >> 7) & (MAIN_ROWS - 1),
                 dirty=int(shadow_state == 'dirty'))
    before = [[mbtb_entry_slot(changed), mbtb_entry_slot(extra) if depth else deepcopy(empty)],
              [clear, deepcopy(empty)]]
    after = deepcopy(before)
    after[0][depth] = mbtb_entry_slot(updated, dirty=1)
    fields = ('set_idx', 'tag', 'branch_type', 'ras_action', 'position', 'carry', 'lower')
    ports = []
    for way, slot in enumerate((mbtb_entry_slot(updated), clear)):
        ports.append(dict(write_valid=1, read_valid=int(way == 1 and shadow_state == 'dirty'),
                          read_ready=1, **{'write_' + field: slot[field] for field in fields}))
    return dict(ports=ports, before=before, after=after, foreign_writes=[])


def observed_mbtb_cleanup_dual(frames, shadows, align, bank):
    """Pair passive native inputs with pre-edge and next-cycle snapshots."""
    by_tick = {frame.event.tick: frame.value['banks'][align][bank] for frame in shadows}
    observations = []
    fields = ('set_idx', 'tag', 'branch_type', 'ras_action', 'position', 'carry', 'lower')
    for frame in frames:
        ports = frame.value['banks'][align][bank]
        if not all(port['write_valid'] for port in ports):
            continue
        tick = frame.event.tick
        foreign = [(other_align, other_bank, way) for other_align, row in enumerate(frame.value['banks'])
            for other_bank, pair in enumerate(row) for way, port in enumerate(pair)
            if (other_align, other_bank) != (align, bank) and port['write_valid']]
        selected = [{key: port[key] for key in ('write_valid', 'read_valid', 'read_ready') + tuple('write_' + field for field in fields)}
                    for port in ports]
        observations.append(dict(tick=tick, value=dict(ports=selected,
            before=by_tick.get(tick), after=by_tick.get(tick + 2), foreign_writes=foreign)))
    return observations
