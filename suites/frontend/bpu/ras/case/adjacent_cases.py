"""Logical traffic shapes; no clock phase, bundle access, or sampled oracle."""


def cases():
    result = []
    for depth in range(1, 5):
        for repeated in (False, True):
            pushes = [dict(action=2, pc=0x98000000 + (0 if repeated else 0x40 * index), position=3)
                for index in range(depth)]
            for profile in ('nested', 'alternate', 'turnaround'):
                if profile == 'nested':
                    operations = pushes + [dict(action=1) for _ in pushes]
                elif profile == 'alternate':
                    operations = [op for push in pushes for op in (push, dict(action=1))]
                else:
                    operations = pushes + [dict(action=1), dict(action=2, pc=0x98000800, position=5)]
                    operations += [dict(action=1) for _ in pushes]
                result.append(dict(label=f'{profile}-depth{depth}-' + ('repeat' if repeated else 'distinct'),
                    operations=operations))
    for count in (9, 10, 12):
        result.append(dict(label=f'saturated-repeat{count}',
            operations=[dict(action=2, pc=0x98001000, position=1) for _ in range(count)]
                + [dict(action=1) for _ in range(count)]))
    return result
