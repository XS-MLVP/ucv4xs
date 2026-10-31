"""Public scenario entry points: no IO phases or task orchestration in tests."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.runtime.artifacts import output_path
from itertools import product

from toffee import CoverageDatabase

from suites.frontend.bpu.abtb.env.state.counter import CounterScenario
from suites.frontend.bpu.abtb.coverage.state.supplemental import ORDERS
from suites.frontend.bpu.abtb.coverage.state.supplemental import capacity_coverage
from suites.frontend.bpu.abtb.coverage.state.supplemental import priority_coverage
from suites.frontend.bpu.abtb.env.state.priority import ResetPriorityScenario
from suites.frontend.bpu.abtb.env.state.replacer import ReplacerScenario
from suites.frontend.bpu.abtb.env.state.writebuffer import WriteBufferScenario
from suites.frontend.bpu.abtb.case.state.scope import bank_index
from suites.frontend.bpu.abtb.case.state.scope import order_axis


async def check_counter_matrix(agent, output, *, bank, sets=range(64)):
    async with CounterScenario(agent, output, bank=bank, sets=tuple(sets)) as scenario:
        for set_index in scenario.sets:
            await scenario.case(set_index)
        await scenario.scrub()
        scenario.coverage.assert_coverage(100.0)
        scenario.gates.assert_coverage(100.0)
    return scenario


async def check_replacer_matrix(agent, output, *, bank, same_set, sets=range(64), victims=range(4)):
    sets, victims = tuple(sets), tuple(victims)
    async with ReplacerScenario(agent, output, bank=bank, same_set=same_set,
                               sets=sets, victims=victims) as scenario:
        for set_index, victim_way in product(sets, victims):
            await scenario.case(set_index=set_index, victim_way=victim_way,
                                epoch=set_index * 4 + victim_way + 1)
        scenario.check(len(sets) * len(victims), len(scenario.cases), phase='all-requested-cases')
        await scenario.scrub()
        scenario.coverage.assert_coverage(100.0)
    return scenario


async def check_reset_training_priority(agent, output, *, bank):
    bank_index(bank)
    coverage = priority_coverage(bank)
    for way, old, taken in product(range(4), range(4), (0, 1)):
        async with ResetPriorityScenario(agent, output, bank=bank, way=way, old=old,
                taken=taken, release_phase=0, coverage=coverage) as scenario:
            scenario.checker.check(1, await scenario.run(), phase='actual-same-cell-collision-required')
    coverage.assert_coverage(100.0)
    write_functional_coverage(CoverageDatabase([coverage]), output_path(output / f'functional-coverage-priority-bank{bank}.json'))
    return coverage


async def check_writebuffer_capacity(agent, output, *, bank, orders=ORDERS):
    bank_index(bank)
    orders = order_axis(orders)
    coverage = capacity_coverage(bank, orders)
    async with WriteBufferScenario(agent, output, bank=bank, order=orders[0], coverage=coverage) as scenario:
        for order in orders:
            await scenario.run(order)
        coverage.assert_coverage(100.0)
    write_functional_coverage(CoverageDatabase([coverage]), output_path(output / f'functional-coverage-capacity-bank{bank}.json'))
    return scenario
