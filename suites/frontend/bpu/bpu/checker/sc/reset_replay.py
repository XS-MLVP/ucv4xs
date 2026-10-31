"""Fresh reset replay of raw SC rising/preedge frames, never live model state."""
from copy import deepcopy
from types import SimpleNamespace
from suites.frontend.bpu.bpu.checker.sc.full import FullScChecker
from suites.frontend.bpu.bpu.model.sc.model import NAMES
from suites.frontend.bpu.bpu.model.sc.model import canonical

def replay(trace, *, fault=None):
    checker = FullScChecker(trace['case'], capacity=len(trace['records']) + 2)
    checker.planned.extend(canonical(deepcopy(trace['transactions'])))
    streams = {'rising': trace['records'], 'preedge': trace['preedge_records']}
    assert len(streams['rising']) == len(streams['preedge']) > 0
    events = sorted(((row['tick'], kind, row) for kind, rows in streams.items() for row in rows))
    assert len({tick for tick, _, _ in events}) == len(events)
    touched = False
    for tick, kind, raw in events:
        checker.phase = raw['phase']
        row = {key: value for key, value in raw.items() if key not in ('tick', 'phase')}
        if fault is not None and (kind, tick) == (fault['stream'], fault['tick']):
            row = deepcopy(row)
            parent = row
            for key in fault['path'][:-1]:
                parent = parent[key]
            parent[fault['path'][-1]] ^= fault.get('mask', 1)
            touched = True
        observation = SimpleNamespace(value=row, event=SimpleNamespace(tick=tick))
        try:
            (checker.observe if kind == 'rising' else checker.observe_controls)(observation)
        except Exception as error:
            error.replay_checker = checker
            error.replay_tick = tick
            raise
    assert fault is None or touched, 'fault must target an actual raw frame'
    return (checker.summary(), checker)

def fault_targets(trace):
    rows = trace['records']
    after_reset = next((row for row in rows if not row['buffers'][NAMES[0]]['reset']))
    first_accept = trace['accepts'][0]['tick']
    main_tick = first_accept + 4
    assert any((row['tick'] == main_tick for row in rows))
    control_tick = first_accept + 3
    targets = [dict(label='PLRU.' + name, stream='rising', tick=after_reset['tick'], path=['replacement', name]) for name in NAMES]
    for way in range(4):
        targets.append(dict(label=f'threshold.{way}', stream='rising', tick=main_tick, path=['used_pipeline', 'thresholds', way]))
        targets.append(dict(label=f'next_threshold.{way}', stream='preedge', tick=control_tick, path=['used_pipeline', 'next_values', way]))
    for name in ('t1_fire', 't2_write_valid'):
        targets.append(dict(label=name, stream='rising', tick=main_tick, path=['used_pipeline', name]))
    targets.append(dict(label='actual_public_taken', stream='rising', tick=first_accept, path=['training', 'bits', 'branches', 0, 'bits', 'taken']))
    seen = set()
    for action in trace['confirmed_actions']:
        if action['kind'] != 'full_overwrite' or (action['buffer'], action['slot']) in seen:
            continue
        name, slot = (action['buffer'], action['slot'])
        seen.add((name, slot))
        lane = next((i for i, mask in enumerate(action['payload']['masks']) if mask))
        for leaf in ('masks', 'data'):
            targets.append(dict(label=f'full_overwrite.{name}.{slot}.{leaf}', stream='rising', tick=action['checked_tick'], path=['buffers', name, 'slots', slot, 'payload', leaf, lane]))
        targets.append(dict(label=f'full_overwrite.{name}.{slot}.dirty', stream='rising', tick=action['checked_tick'], path=['buffers', name, 'slots', slot, 'dirty']))
    return targets
