"""Deterministic long-first pairs for xdist's two-item initial lookahead.

Pair each hinted scenario with an unhinted contract check, when available.
This changes only collection order; no custom scheduler, grouping or selection.
"""
import math

import pytest


def _contract_filler(item):
    # fixturenames includes pytest's transitive fixture closure. Never use a
    # feature scenario or a DUT/agent consumer as the supposedly cheap second
    # item. Missing closure information fails closed (e.g. synthetic items).
    fixtures = getattr(item, 'fixturenames', None)
    return (fixtures is not None and item.get_closest_marker('feature') is None
            and not any('dut' in name.lower() or name.lower() == 'agent'
                        or name.endswith('_agent') for name in fixtures))


def order_tests(items):
    costs = []
    for item in items:
        marker = item.get_closest_marker('estimated_runtime')
        if marker is None:
            costs.append(0)
            continue
        if (len(marker.args) != 1 or marker.kwargs
                or type(marker.args[0]) not in (int, float)
                or (isinstance(marker.args[0], float) and not math.isfinite(marker.args[0]))
                or marker.args[0] < 0):
            raise pytest.UsageError(f'{item.nodeid}: estimated_runtime needs one finite nonnegative number of seconds')
        costs.append(marker.args[0])
    # Validate all hints before changing any collection. Equal-cost items keep
    # their original order, identically in collection/controller/every worker.
    ordered = sorted(zip(items, costs, strict=True), key=lambda pair: -pair[1])
    scenarios = [item for item, cost in ordered if cost > 0]
    fillers = [item for item, cost in ordered if cost == 0 and _contract_filler(item)]
    pairs, used = [], set()
    for index, scenario in enumerate(scenarios):
        pairs.append(scenario)
        used.add(id(scenario))
        if index < len(fillers):
            pairs.append(fillers[index])
            used.add(id(fillers[index]))
    # Preserve stable original ordering for every remaining zero-cost item.
    items[:] = pairs + [item for item, cost in ordered if id(item) not in used]
