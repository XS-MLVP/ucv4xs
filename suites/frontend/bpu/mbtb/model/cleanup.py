"""Bounded, independent MainBTB multi-hit cleanup plus retarget expectations."""
from suites.frontend.bpu.models.configuration import *
from copy import deepcopy
from dataclasses import replace
from suites.frontend.bpu.mbtb.model.replacement import MbtbFourWayLru


def cleanup_way_plan():
    """Reset LRU intent for two distinct rows; never use observed owner bits.

    Original/displacer are the first allocations in their separate LRU cells.
    Replayed cold correction and the extra neighbor are the second allocations.
    Changing their relative submission order cannot change either cell's plan.
    """
    original, neighbor = MbtbFourWayLru(), MbtbFourWayLru()
    first, displacer = original.allocate(), neighbor.allocate()
    changed, extra = original.allocate(), neighbor.allocate()
    return dict(original=first, displacer=displacer, changed=changed, extra=extra,
                keep=min(first, changed), clear=max(first, changed))


def expected_mbtb_cleanup_states(duplicate, neighbor, pc, align, keep_way, clear_way,
                                 neighbor_way, target):
    """Keep the lower duplicate, clear the upper and retarget another set.

    The prepared indirect residents have weak-positive counters. Cleanup does
    not initialize counters, and a same-attribute indirect retarget preserves
    them. Inputs are immutable full public profiles, not encoder output.
    """
    for way in (keep_way, clear_way, neighbor_way):
        if type(way) is not int or way not in range(MAIN_WAYS):
            raise ValueError('cleanup requires physical ways')
    if align not in (0, 1) or keep_way == clear_way:
        raise ValueError('cleanup requires a physical align bank and two duplicate ways')
    lower, upper = (align * (MAIN_WAYS + 1) + keep_way,
                    align * (MAIN_WAYS + 1) + clear_way)
    if keep_way > clear_way:
        raise ValueError('cleanup preserves the lower duplicate way')
    entries = duplicate['entries']
    if len(entries) != RESULT_SLOTS or any(entry.valid for index, entry in enumerate(entries) if index not in (lower, upper)):
        raise ValueError('cleanup requires exactly two active duplicate ways')
    if not all(entries[index].valid and entries[index].branch_type == 3 for index in (lower, upper)) or entries[lower].position != entries[upper].position:
        raise ValueError('cleanup requires same-position indirect duplicates')
    if any(duplicate['meta_entries'][align][way]['counter_value'] != 2 for way in (keep_way, clear_way)):
        raise ValueError('cleanup reference requires weak-positive duplicate counters')
    active = align * (MAIN_WAYS + 1) + neighbor_way
    chosen = neighbor['entries'][active]
    if not chosen.valid or chosen.branch_type != 3 or neighbor['meta_entries'][align][neighbor_way]['counter_value'] != 2:
        raise ValueError('cleanup reference requires a weak-positive indirect neighbor')
    cleaned, updated = deepcopy(duplicate), deepcopy(neighbor)
    cleaned['entries'] = tuple(replace(entry, valid=0, target=pc & ~((1 << 20) - 1),
        position=align * ALIGN_HALFWORDS, branch_type=0, ras_action=0) if index == upper else entry
        for index, entry in enumerate(entries))
    cleaned['meta_entries'][align][clear_way].update(rawHit=0, position=align * ALIGN_HALFWORDS,
        counter_value=2)
    # A destination clear writes the all-zero MainBtbEntry, including its
    # attribute. The old two-way expected profile accidentally kept kind=3.
    cleaned['meta_entries'][align][clear_way]['attribute'] = dict(branchType=0, rasAction=0)
    updated['entries'] = tuple(replace(entry, target=target) if index == active else entry
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
    """Predict both active writes and all four ways × four retained slots."""
    if depth not in (0, 1) or shadow_state not in ('dirty', 'clean'):
        raise ValueError('cleanup native reference requires depth zero/one and dirty/clean')
    empty = dict(valid=0, dirty=0, set_idx=0, tag=0, position=0,
                 branch_type=0, ras_action=0, carry=0, lower=0)
    clear = dict(empty, valid=1, set_idx=(original.pc >> 7) & (MAIN_ROWS - 1),
                 dirty=int(shadow_state == 'dirty'))
    plan = cleanup_way_plan()
    update_way, clear_way = plan['extra'], plan['clear']
    assert plan['changed'] == update_way and update_way != clear_way
    before = [[deepcopy(empty) for _ in range(MAIN_RETAINED)] for _ in range(MAIN_WAYS)]
    before[update_way][0] = mbtb_entry_slot(changed)
    if depth:
        before[update_way][depth] = mbtb_entry_slot(extra)
    before[clear_way][0] = clear
    after = deepcopy(before)
    after[update_way][depth] = mbtb_entry_slot(updated, dirty=1)
    fields = ('set_idx', 'tag', 'branch_type', 'ras_action', 'position', 'carry', 'lower')
    ports = []
    for way in range(MAIN_WAYS):
        slot = mbtb_entry_slot(updated) if way == update_way else clear if way == clear_way else None
        port = dict(write_valid=int(slot is not None),
                    read_valid=int(way == clear_way and shadow_state == 'dirty'), read_ready=1)
        if slot is not None:
            port.update({'write_' + field: slot[field] for field in fields})
        ports.append(port)
    return dict(ports=ports, before=before, after=after, foreign_writes=[])


def observed_mbtb_cleanup_dual(frames, shadows, align, bank):
    """Pair passive native inputs with pre-edge and next-cycle snapshots."""
    by_tick = {frame.event.tick: frame.value['banks'][align][bank] for frame in shadows}
    observations = []
    fields = ('set_idx', 'tag', 'branch_type', 'ras_action', 'position', 'carry', 'lower')
    for frame in frames:
        ports = frame.value['banks'][align][bank]
        if sum(bool(port['write_valid']) for port in ports) < 2:
            continue
        tick = frame.event.tick
        foreign = [(other_align, other_bank, way) for other_align, row in enumerate(frame.value['banks'])
            for other_bank, pair in enumerate(row) for way, port in enumerate(pair)
            if (other_align, other_bank) != (align, bank) and port['write_valid']]
        selected = [{key: port[key] for key in ('write_valid', 'read_valid', 'read_ready') +
                    (tuple('write_' + field for field in fields) if port['write_valid'] else ())}
                    for port in ports]
        observations.append(dict(tick=tick, value=dict(ports=selected,
            before=by_tick.get(tick), after=by_tick.get(tick + 2), foreign_writes=foreign)))
    return observations
