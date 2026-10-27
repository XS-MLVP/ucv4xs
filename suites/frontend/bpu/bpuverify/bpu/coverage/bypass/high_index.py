"""Reset-derived high useful roles, earned only after complete state replay."""
from types import SimpleNamespace

from bpuverify.bpu.checker.bypass.checker import BypassChecker


def collect_updates(frames, *, index=462, tag=208, position=6):
    """The caller separately checks parent policy and genuine public metadata.

    No observed useful value seeds expected state; both tables are replayed.
    This collector alone does not establish integrated input legality.
    """
    for name, value, limit in (('index', index, 512), ('tag', tag, 256), ('position', position, 16)):
        if type(value) is not int or value not in range(limit):
            raise ValueError(f'invalid high-row {name}')
    if not frames:
        raise ValueError('complete reset-derived shadow frames required')
    checker, updates, pending = BypassChecker(), [], None
    for frame in frames:
        row, tick, phase = frame['value'], frame['tick'], frame['phase']
        reference = checker.references[0]
        inputs = row['tables'][0]['inputs']
        before = reference.useful[index]
        relevant = (phase == 'preedge' and not row['reset'] and reference.train_index == index
            and inputs['tag'] == tag and (inputs['allocate'] or inputs['update'])
            and (inputs['allocate_position'] if inputs['allocate'] else inputs['update_position']) == position)
        checker.observe(phase, SimpleNamespace(event=SimpleNamespace(tick=tick), value=row))
        if phase == 'rising' and pending is not None:
            # A computed next state alone is not an observed successful effect.
            updates.append(pending)
            pending = None
        if relevant:
            role = ('allocation' if inputs['allocate'] else
                'agreement-hold' if not inputs['useful_valid'] else
                'increase' if inputs['useful_increase'] else 'decrease')
            if inputs['age']:
                raise AssertionError('global aging is outside this local update-role scenario')
            expected = (1 if role == 'allocation' else before if role == 'agreement-hold' else
                min(3, before + 1) if role == 'increase' else max(0, before - 1))
            checker.check(expected, reference.useful[index], table=0, point='independent high-row useful role')
            pending = dict(tick=tick, role=role, index=index, tag=tag, position=position,
                before=before, after=expected, inputs=dict(inputs))
    checker.finish()
    return updates
