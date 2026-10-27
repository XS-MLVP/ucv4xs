"""Legacy implementation-level MicroRAS diagnostic in halfword units.

The main RAS top is an input to this module, not expected state seeded from
its output. This reference does not model the main speculative RAS stack.
It mirrors the implementation's register transitions and is NOT the event-level
golden model. New functional comparisons use model.semantic.UrasReference.
"""
from copy import deepcopy

MASK = (1 << 50) - 1


def empty_state():
    return dict(s2_push=0, s2_pop=0, s3_push=0, s3_pop=0, s2_address=0,
        s3_address=0, usable=0, address=0, delayed_redirect=0)


def return_address(operation):
    return ((operation['pc'] & ~7) + operation['position'] + 1) & MASK


def selected_output(state, inputs):
    """Resolve younger operations against older pending operations."""
    s1, s2, s3 = (inputs[stage] for stage in ('s1', 's2', 's3'))
    main = inputs['main_top']
    recovering = bool(state['delayed_redirect'])
    usable, address, route = state['usable'], state['address'], 'hold'
    if inputs['redirect']:
        return 0, address, 'redirect'
    if s3['valid']:
        usable = int(s3['action'] != 1)
        address = 0 if s3['action'] == 1 else return_address(s3) if s3['action'] == 2 else main
        return usable, address, 's3-correction'
    if s2['valid']:
        if s2['action'] == 2:
            return 1, return_address(s2), 's2-call-correction'
        if s2['action'] == 1:
            return state['s3_push'], main if state['s3_push'] else 0, 's2-return-correction'
        if state['s3_push']:
            return 1, state['s3_address'], 's2-neutral/s3-push'
        if state['s3_pop']:
            return 0, address, 's2-neutral/s3-pop'
        return int(not recovering), 0 if recovering else main, 's2-neutral/main'
    if not inputs['fire1']:
        return usable, address, route
    if s1['action'] == 2:
        return 1, return_address(s1), 's1-call'
    if s1['action'] == 1:
        if state['s2_push']:
            if state['s3_push']:
                return 1, state['s3_address'], 's1-pop/s2-push/s3-push'
            if state['s3_pop']:
                return 0, 0, 's1-pop/s2-push/s3-pop'
            return 1, main, 's1-pop/s2-push/main'
        if state['s2_pop']:
            return 0, address, 's1-pop/s2-pop'
        if state['s3_push']:
            return 1, main, 's1-pop/s3-push'
        return 0, address, 's1-pop/no-pair'
    if state['s2_push']:
        return 1, state['s2_address'], 's1-neutral/s2-push'
    if state['s2_pop']:
        return state['s3_push'], main if state['s3_push'] else 0, 's1-neutral/s2-pop'
    if state['s3_pop']:
        return 0, address, 's1-neutral/s3-pop'
    if state['s3_push']:
        return 1, state['s3_address'], 's1-neutral/s3-push'
    return int(not recovering), 0 if recovering else main, 's1-neutral/main'


def advance(state, inputs, reset=0):
    if reset:
        return empty_state(), 'reset'
    result = deepcopy(state)
    s1, s2, s3 = (inputs[stage] for stage in ('s1', 's2', 's3'))
    flush = inputs['redirect'] or s3['valid']
    if flush:
        result.update(s2_push=0, s2_pop=0, s3_push=0, s3_pop=0)
    else:
        if s2['valid']:
            result.update(s2_push=int(not inputs['fire2'] and s2['action'] == 2),
                s2_pop=int(not inputs['fire2'] and s2['action'] == 1))
        elif inputs['fire1']:
            result.update(s2_push=int(s1['action'] == 2), s2_pop=int(s1['action'] == 1))
        elif inputs['fire2']:
            result.update(s2_push=0, s2_pop=0)
        if inputs['fire2']:
            result.update(s3_push=int(s2['action'] == 2) if s2['valid'] else state['s2_push'],
                s3_pop=int(s2['action'] == 1) if s2['valid'] else state['s2_pop'])
        elif inputs['fire3']:
            result.update(s3_push=0, s3_pop=0)
    if inputs['fire1'] and not s2['valid'] and s1['action'] == 2:
        result['s2_address'] = return_address(s1)
    if inputs['fire2']:
        result['s3_address'] = return_address(s2) if s2['valid'] else state['s2_address']
    if s2['valid'] and not inputs['fire2'] and s2['action'] == 2:
        result['s2_address'] = return_address(s2)
    result['usable'], result['address'], route = selected_output(state, inputs)
    result['delayed_redirect'] = inputs['redirect']
    return result, route
