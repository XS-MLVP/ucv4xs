"""One sparse conditional geometry, with separate index and tag ancestry.

Each A -> B -> C -> D -> A cycle contains one conditional branch. A's
not-taken path uses a later unconditional CFI to the same B, not a fictitious
fall-through. These are input-only predictions; runtime stalls and overrides
must still pass the independent index pipeline checker.
"""
from suites.frontend.bpu.models.configuration import PHR_STORAGE_BITS, PHR_FOLDS
from collections import Counter

HISTORY_ROUNDS = (PHR_STORAGE_BITS+7)//8+2

from suites.frontend.bpu.bpu.case.bypass.history_plan import full_tags, read_indices
from suites.frontend.bpu.bpu.model.abtb.alias import boundary, mainbtb_route
from suites.frontend.bpu.bpu.model.abtb.final_not_taken import advance_scalar
from suites.frontend.bpu.bpu.model.bypass.index import IndexPipeline
from suites.frontend.bpu.bpu.model.phr.model import BpuPhrReference, fold, folds


def edges(program, taken):
    a, b, c, d = program['nodes']
    return ((a, b, 6 if taken else 10), (b, c, 7), (c, d, 7), (d, a, 7))


def phase_contexts(program, taken):
    """Scalar full-history and explicit two-earlier-request queue, no DUT."""
    history, requests, contexts = 0, [], {}
    # Flush the entire configured circular history with four taken edges per round.
    for round_ in range(HISTORY_ROUNDS):
        for pc, target, position in edges(program, taken):
            normal_folds = (fold(history, 5, 5), fold(history, 9, 9))
            if round_ == HISTORY_ROUNDS-1:
                context = requests[-2]
                contexts[pc] = dict(history=history, index_pc=context['pc'],
                    index_folds=context['folds'], indices=context['indices'], target=target, position=position)
            requests.append(dict(pc=target, folds=normal_folds,
                                 indices=read_indices(target, normal_folds)))
            history = advance_scalar(history, pc, target, position, 1)
    nodes = program['nodes']
    for pc, previous in zip(nodes, nodes[-1:] + nodes[:-1], strict=True):
        # The tag is checked/captured when the PREVIOUS S1 selects this PC.
        # It is not the later PHR snapshot in this PC's public redirect meta.
        contexts[pc]['tag_history'] = contexts[previous]['history']
        contexts[pc]['tags'] = full_tags(pc, folds(contexts[pc]['tag_history']))
    return contexts


def recipe():
    programs = []
    residents = []
    for offset in (0, 64):
        nodes = tuple(0x40010006 + offset + 16 * i for i in range(4))
        program = dict(pc=nodes[0], target=nodes[1], position=6, fallback=10, nodes=nodes)
        program['positive'] = phase_contexts(program, True)
        program['negative'] = phase_contexts(program, False)
        programs.append(program)
        residents.extend(edges(program, True))
        residents.append(edges(program, False)[0])
    counts = Counter()
    for pc, _, position in residents:
        route = mainbtb_route(pc, position)
        counts[(route['selected_physical_align'], route['internal_bank'], route['entry_set'])] += 1
    if max(counts.values()) > 4:
        raise AssertionError('sparse program exceeds genuine MainBTB capacity')
    for program in programs:
        for phase in ('positive', 'negative'):
            ctx = program[phase][program['pc']]
            if not all(tag < 256 for tag in ctx['tags']):
                raise AssertionError('sparse A tag cannot fit the hardware payload')
            if ctx['index_pc'] != program['nodes'][3]:
                raise AssertionError('A index must originate from the earlier C -> D request')
    return dict(old=programs[0], second=programs[1], conditional_density='1 of 4 accepted requests',
                MainBTB_residents=len(residents), maximum_MainBTB_residents_per_group=max(counts.values()))


def joint_proof(program):
    """Check the scalar prediction against full PHR and fire-based registers."""
    history, model, index, tick, checks = 0, BpuPhrReference(), IndexPipeline(), 0, 0
    previous_history = None
    for taken in (False, True, False, True):
        for round_ in range(HISTORY_ROUNDS):
            for pc, target, position in edges(program, taken):
                if round_ == HISTORY_ROUNDS-1:
                    wanted = program['positive' if taken else 'negative'][pc]
                    if (history, index.a2['pc'], index.a2['folds'], index.a2['indices']) != (
                            wanted['history'], wanted['index_pc'], wanted['index_folds'], wanted['indices']):
                        raise AssertionError('joint history/index disagrees with scalar input geometry')
                    if previous_history != wanted['tag_history']:
                        raise AssertionError('tag must use the previous S1 request history')
                index.advance(reset=0, enable=1, fire0=1, fire2=1, s2=0, s3=0,
                    pc=target, normal_folds=(fold(history, 5, 5), fold(history, 9, 9)), tick=tick)
                inputs = boundary(model, pc, target)
                inputs['s1']['prediction'].update(position=position, taken=1)
                model.advance(inputs, reset=0)
                previous_history = history
                history = advance_scalar(history, pc, target, position, 1)
                if model.logical() != history or model.state['fold1'] != folds(history):
                    raise AssertionError('full PHR disagrees with independent scalar advance')
                tick += 1
                checks += 1
    return checks


def qualifies_return_request(token, hash_inputs, *, program, after_tick, phase='positive'):
    """Separate the older index request from the current A tag request."""
    context = program[phase][program['pc']]
    tag_folds = folds(context['tag_history'])
    return bool(token is not None and token['source_tick'] is not None
        and token['source_tick'] > after_tick and token['pc'] == context['index_pc']
        and token['folds'] == context['index_folds'] and token['indices'] == context['indices']
        and hash_inputs['new_pc'] == program['pc']
        and hash_inputs['s1_folds'] == tuple(tag_folds[i] for i in (PHR_FOLDS.index(p) for p in ((5,4),(5,5),(9,7),(9,8))))
        and not any(hash_inputs[name] for name in ('redirect_valid', 's2_override', 's3_override')))
