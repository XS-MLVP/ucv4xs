"""suites.frontend.bpu.bpu.case.sc.supplemental components."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage

from suites.frontend.bpu.runtime.artifacts import output_path
from toffee import CoverageDatabase
from suites.frontend.bpu.bpu.case.sc.scenarios import run_case


async def verify_with_coverage(agent, execution, output, case, group):
    await run_case(agent, execution, output, case)
    group.sample(dict(bank=case['bank'], row=case['row'],
        pair='_'.join(map(str, case['positions'])), order=case['order'], lifecycle=case['lifecycle']))
    write_functional_coverage(CoverageDatabase([group]), output_path(output / 'functional-coverage-sc-masked-feedback.json'))


async def check_masked_feedback(agent, output, case, group):
    """Intent-level entry point; component owns Execution and passive sampling."""
    if agent._execution is None:
        raise RuntimeError("SC feedback checks require a started BpuAgent")
    await verify_with_coverage(agent, agent._execution, output, case, group)
