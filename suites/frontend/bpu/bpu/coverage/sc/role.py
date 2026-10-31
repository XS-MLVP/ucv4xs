"""suites.frontend.bpu.bpu.coverage.sc.role components."""

from itertools import combinations
from itertools import product
from math import prod
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CrossDef
from suites.frontend.bpu.bpu.model.sc.provider_roles import PROFILES


def cases():
    return [dict(bank=bank, positions=list(pair), keys=4, key_order=key_order,
                 mask_order=mask_order, provider_profile=profile, lifecycle='dirty_then_clean')
            for profile, bank, pair, key_order, mask_order in product(
                PROFILES, (0, 1), combinations((4, 5, 6, 7), 2), ('forward', 'reverse'), ('forward', 'reverse'))]


def group(name, axes):
    points = tuple(CoverPointDef(axis, {str(value): Bin.values(value) for value in values})
                   for axis, values in axes.items())
    return CoverGroupDef(name, points, crosses=(CrossDef(name + '_cross', tuple(axes),
        max_auto_bins=prod(map(len, axes.values()))),)).instantiate('kunminghu_v3.bpu.' + name)


def matrix_coverage():
    return group('sc_four_key_provider_roles',
        dict(bank=(0, 1), pair=tuple(f'{a}_{b}' for a, b in combinations((4, 5, 6, 7), 2)),
             key_order=('forward', 'reverse'), mask_order=('forward', 'reverse'),
             provider_profile=tuple(PROFILES), table=('pathTable_0', 'imliTable', 'biasTable'),
             slot=(0, 1, 2, 3), lifecycle=('dirty_merge', 'clean_reactivate')))


def physical_bias_coverage():
    return group('sc_four_key_physical_bias_lanes',
        dict(bank=(0, 1), way=tuple(range(16)), slot=(0, 1, 2, 3),
             lifecycle=('dirty_merge', 'clean_reactivate')))


def qualified_samples(trace):
    case = trace['case']
    qualified = {(row['buffer'], row['slot'], row['kind']) for row in trace['witnesses']}
    assert len(qualified) == 24
    abstract = []
    for buffer, slot, lifecycle in sorted(qualified):
        table, bank = buffer.rsplit('_bank', 1)
        assert int(bank) == case['bank']
        abstract.append(dict(bank=case['bank'], pair='_'.join(map(str, case['positions'])),
            key_order=case['key_order'], mask_order=case['mask_order'],
            provider_profile=case['provider_profile'], table=table, slot=slot, lifecycle=lifecycle))
    bias = set()
    for row in trace['records']:
        if not row['phase'].startswith('drive_'):
            continue
        buffer = row['buffers'][f"biasTable_bank{case['bank']}"]
        if not buffer['write']['valid']:
            continue
        for slot, entry in enumerate(buffer['slots']):
            if entry['valid'] and entry['payload']['set_index'] == buffer['write']['bits']['set_index']:
                lifecycle = 'dirty_merge' if entry['dirty'] else 'clean_reactivate'
                selected, = [way for way, mask in enumerate(buffer['write']['bits']['masks']) if mask]
                bias.add((selected, slot, lifecycle))
    assert len(bias) == 8
    physical = [dict(bank=case['bank'], way=way, slot=slot, lifecycle=lifecycle)
                for way, slot, lifecycle in sorted(bias)]
    return abstract, physical
