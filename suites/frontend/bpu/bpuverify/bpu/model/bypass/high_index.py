"""One genuine four-node program with high index and representable lower tag."""
from collections import Counter
from bpuverify.bpu.model.abtb.alias import mainbtb_route, physical_index
from bpuverify.bpu.model.bypass.sparse import edges, phase_contexts


HIGH_INDEX_ROLES = ('allocation', 'increase', 'decrease', 'agreement-hold')


def program():
    nodes = (0x40010006, 0x40010016, 0x40010080, 0x400101E2)
    value = dict(pc=nodes[0], target=nodes[1], position=6, fallback=10, nodes=nodes)
    for name, taken in (('positive', True), ('negative', False)):
        value[name] = phase_contexts(value, taken)
        context = value[name][value['pc']]
        if context['indices'][0] != 494 or context['tags'][0] != 112 or context['index_pc'] != nodes[3]:
            raise AssertionError('high index / low lower-tag ancestry changed')
    counts = Counter()
    for pc, _, position in (*edges(value, True), edges(value, False)[0]):
        route = mainbtb_route(pc, position)
        counts[route['selected_physical_align'], route['internal_bank'], route['entry_set']] += 1
    if max(counts.values()) > 2:
        raise AssertionError('the five genuine MainBTB residents must fit without eviction')
    return value


def base_alias(value):
    """One extra return node preserves ABTB index but separates UTAGE keys."""
    a, b, c, d = value['nodes']
    alias = dict(value, nodes=(a, b, c + 32, d))
    for phase, taken in (('positive', True), ('negative', False)):
        alias[phase] = phase_contexts(alias, taken)
        original, alternate = value[phase][a], alias[phase][a]
        if physical_index(original['index_pc'], original['index_folds'][0]) != physical_index(
                alternate['index_pc'], alternate['index_folds'][0]):
            raise AssertionError('base alias must preserve the complete ABTB index')
        if any(left == right for left, right in zip(original['indices'], alternate['indices'], strict=True)):
            raise AssertionError('base alias must separate both MicroTAGE indices')
    residents = set((*edges(value, True), edges(value, False)[0],
        *edges(alias, True), edges(alias, False)[0]))
    counts = Counter()
    # Retargeting B replaces its target in place, not an additional resident.
    for pc, position in {(pc, position) for pc, _, position in residents}:
        route = mainbtb_route(pc, position)
        counts[route['selected_physical_align'], route['internal_bank'], route['entry_set']] += 1
    if max(counts.values()) > 2:
        raise AssertionError('base-alias program exceeds genuine MainBTB capacity')
    return alias
