"""Integrated retirement intent and successful, input-derived functional coverage."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.runtime.artifacts import output_path
import json
from suites.frontend.bpu.runtime.trace import dump_trace
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import Scoreboard
from suites.frontend.bpu.bpu.case.ras.nested import run_nested
from suites.frontend.bpu.bpu.case.ras.deep import run_chain
from suites.frontend.bpu.bpu.case.ras.repeat import run_repeated_calls


CASES = (('nested', 0), ('deep', 4), ('deep', 7), ('deep', 8), ('repeat', 9), ('repeat', 10))


def retirement_coverage():
    return CoverGroupDef('integrated_ras_retirement', (
        CoverPointDef('intent', {f'{kind}-{count}': Bin.values(f'{kind}-{count}') for kind, count in CASES}),
        CoverPointDef('action', {'return': Bin.values(1), 'call': Bin.values(2)}),
    )).instantiate('kunminghu_v3.bpu.integrated_ras_retirement')


async def check_retirement_case(agent, output, *, kind, count=0):
    if (kind, count) not in CASES:
        raise ValueError(f'unsupported retirement intent: {kind!r}, count={count!r}')
    if kind == 'nested':
        trace = await run_nested(agent)
    elif kind == 'deep':
        trace = await run_chain(agent, count)
    else:
        trace = await run_repeated_calls(agent, count)
    # All source association, full-state comparison, PHR checking and drain
    # take place in the reusable retirement context before it returns.
    board = Scoreboard('bpu.integrated_retirement_coverage')
    board.check(expected=len(trace['accepted']), actual=len(trace['applied']))
    board.check(expected=trace['summary']['accepted'], actual=len(trace['accepted']))
    board.check(expected=trace['summary']['applied'], actual=len(trace['applied']))
    # Depth8 evicts the reset sentinel and has only seven legal returns.
    # An eighth return would invent bottom/empty-stack behavior outside scope.
    expected_count = 4 if kind == 'nested' else count + min(count, 7) if kind == 'deep' else trace['actual_calls']
    board.check(expected=expected_count, actual=len(trace['accepted']))
    if not trace['accepted']:
        raise ValueError('retirement coverage requires actual accepted commit requests')
    actions = [entry['request']['action'] for entry in trace['accepted']]
    if any(action not in (1, 2) for action in actions):
        raise ValueError('retirement coverage requires actual call/return inputs')
    coverage = retirement_coverage()
    case = f'{kind}-{count}'
    for action in actions:
        coverage.sample(dict(intent=case, action=action))
    artifact = output / f'integrated-retirement-{case}'
    artifact.mkdir(parents=True, exist_ok=True)
    dump_trace((artifact / 'trace.json'), trace)
    write_functional_coverage(CoverageDatabase((coverage,)), output_path(output / f'functional-coverage-integrated-retirement-{case}.json'))
    return trace['summary']
