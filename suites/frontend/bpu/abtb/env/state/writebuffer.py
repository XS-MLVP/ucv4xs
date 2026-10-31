"""suites.frontend.bpu.abtb.env.state.writebuffer components."""

from copy import deepcopy
from dataclasses import asdict
from dataclasses import replace
from suites.frontend.bpu.runtime.trace import dump_trace
from toffee import ClockCycles
from suites.frontend.bpu.abtb.transaction.types import AbtbTraining
from suites.frontend.bpu.abtb.case.state.vectors import interior_set_vectors
from suites.frontend.bpu.abtb.model.state.counter import index
from suites.frontend.bpu.abtb.case.state.counter import packed
from suites.frontend.bpu.abtb.driver.state.training_driver import AcceptedPulseDriver
from suites.frontend.bpu.abtb.env.state.session import StateObservation
from suites.frontend.bpu.abtb.case.state.scope import bank_index
from suites.frontend.bpu.abtb.case.state.scope import order_axis
from suites.frontend.bpu.abtb.checker.state.writebuffer import CapacityChecker
from suites.frontend.bpu.abtb.monitor.state.writebuffer import CapacityMonitor
from suites.frontend.bpu.abtb.case.state.writebuffer import SETS


class WriteBufferScenario:
    def __init__(self, agent, output, *, bank, order, coverage):
        bank_index(bank)
        order_axis((order,))
        self.agent, self.output, self.bank, self.order = agent, output, bank, order
        self.coverage = coverage
        self.checker = CapacityChecker(scope=f'bank{bank}-{order}')
        self.monitor = CapacityMonitor(agent)
        self.driver = AcceptedPulseDriver(agent.ports.training, checker=self.checker)
        self.observation = StateObservation(agent, self.monitor, self.checker, driver=self.driver)
        self.intents, self.profiles, self.witnesses = [], [], []
        self.completed_orders, self.case_windows, self.metadata_ticks = [], [], {}

    async def __aenter__(self):
        await self.observation.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.observation.__aexit__(exc_type, exc, traceback)
        records = []
        for row in self.checker.records:
            compact = deepcopy(row)
            compact['counter']['cells'] = packed(compact['counter']['cells'])
            records.append(compact)
        report = dict(bank=self.bank, orders=self.completed_orders, case_windows=self.case_windows, intents=self.intents,
            profiles=self.profiles, witnesses=self.witnesses, records=records,
            actions=self.checker.actions, drains=self.checker.drains,
            failure=None if self.checker.failure is None and exc is None else repr(self.checker.failure or exc), trace_kind='abtb-writebuffer-state')
        if exc_type is None:
            report['summary'] = self.checker.summary()
        dump_trace((self.output / f'capacity-bank{self.bank}.json'), report)

    async def predict(self, vector, *, phase):
        actual = await self.agent.predict(vector.pc, path_hash=self.bank)
        self.checker.raise_failure()
        bank, s = self.bank, (((vector.pc << 1) ^ self.bank) & 255) >> 2
        check, ref = self.checker.check, self.checker.reference
        check((1, 1 << bank, s), (actual.meta['valid'], actual.meta['bankMask'], actual.meta['setIdx']),
              phase=phase + '.meta-route')
        expected = []
        for way, entry in enumerate(actual.entries):
            resident = ref.sram[bank][s][way]
            valid = int(bool(resident['valid'] and resident['tag'] == vector.pc & ((1 << 24) - 1)))
            check((valid, valid, valid), (entry.valid, actual.meta['entries'][way]['hit'],
                actual.micro_tage['result'][way]['valid']), phase=phase + '.valid-hit', way=way)
            if valid:
                counter = ref.counter.cells[index(bank, s, way)]
                wanted = dict(valid=1, taken=int(counter >= 2),
                    target=(vector.pc & ~((1 << 22) - 1)) | resident['target_low'],
                    position=resident['position'], branch_type=resident['branch_type'], ras_action=resident['ras_action'])
                check(wanted, asdict(entry), phase=phase + '.full-entry', way=way)
                attribute = dict(branchType=resident['branch_type'], rasAction=resident['ras_action'])
                check(dict(taken=int(counter >= 2), attribute_branchType=resident['branch_type']),
                    actual.micro_tage['result'][way]['bits'], phase=phase + '.direction', way=way)
                check((resident['position'], resident['target_low'], attribute),
                    (actual.meta['entries'][way]['position'], actual.meta['entries'][way]['targetLowerBits'],
                     actual.meta['entries'][way]['attribute']), phase=phase + '.metadata-identity', way=way)
                expected.append(dict(way=way, counter=counter, entry=wanted))
        self.profiles.append(dict(phase=phase, pc=vector.pc, set_index=s,
            checked_tick=self.checker.last_tick, expected=expected, actual=asdict(actual)))
        self.metadata_ticks[id(actual)] = self.checker.last_tick
        return actual

    def submit(self, vector, prediction, *, phase):
        tx = AbtbTraining(pc=vector.pc, target=vector.target, taken=1, position=vector.position,
                          branch_type=vector.branch_type, meta=deepcopy(prediction.meta))
        self.checker.plan(tx)
        self.intents.append(dict(after_tick=self.checker.last_tick, phase=phase, request=asdict(tx),
                                 metadata_tick=self.metadata_ticks[id(prediction)]))
        return self.driver.send(self.agent.encode_training(tx))

    def checkpoint(self, phase, *, dirty):
        self.checker.raise_failure()
        buffer = self.checker.reference.buffers[self.bank]
        self.checker.check([dirty] * 4, [slot['dirty'] for slot in buffer.slots], phase=phase + '.all-four-slots')
        self.checker.check([1] * 4, [slot['shadow_valid'] for slot in buffer.slots], phase=phase + '.all-shadow-valid')
        for slot, state in enumerate(buffer.slots):
            self.witnesses.append(dict(tick=self.checker.last_tick, bank=self.bank, order=self.order,
                slot=slot, phase=phase, actual=deepcopy(self.checker.records[-1]['banks'][self.bank]['slots'][slot]),
                independently_checked_state=deepcopy(state)))
            self.coverage.sample(dict(bank=self.bank, order=self.order, slot=slot, phase=phase))

    async def run(self, order=None):
        if order is not None:
            order_axis((order,))
            self.order = order
        self.checker.scope = f'bank{self.bank}-{self.order}'
        if self.completed_orders:
            await self.agent.reset()
            self.checker.raise_failure()
        drain_begin, action_begin = len(self.checker.drains), len(self.checker.actions)
        window = dict(order=self.order, sets=SETS[self.order], begin_tick=self.checker.last_tick,
                      drain_begin=drain_begin, action_begin=action_begin)
        vectors = tuple(replace(interior_set_vectors(self.bank, s, count=1)[0],
            target=0x40090000 + self.bank * 0x10000 + s * 0x100) for s in SETS[self.order])
        cold = [await self.predict(vector, phase='genuine-cold') for vector in vectors]
        transfers = [self.submit(vector, prediction, phase='four-pending-allocations')
                     for vector, prediction in zip(vectors, cold, strict=True)]
        for transfer in transfers:
            await transfer
        # All requests travel through the two-stage public feedback path;
        # clock waits are hidden in this reusable experiment, not in testcases.
        await ClockCycles(self.agent.dut.clock, 4)
        still_cold = [await self.predict(vector, phase='pending-still-cold') for vector in vectors]
        self.checkpoint('pending', dirty=1)
        self.checker.check(drain_begin, len(self.checker.drains), phase='none-drained-under-read-pressure')
        rewritten = tuple(replace(vector, target=vector.target + 0x40, position=3) for vector in vectors)
        for vector, prediction in zip(rewritten, still_cold, strict=True):
            await self.submit(vector, prediction, phase='same-key-dirty-rewrite')
        await ClockCycles(self.agent.dut.clock, 4)
        self.checkpoint('dirty_rewrite', dirty=1)
        self.checker.check(4, sum(item['role'] == 'dirty_hit' for item in self.checker.actions[action_begin:]), phase='four-actual-dirty-hits')
        await self.agent.drain_bank_writes()
        for vector in rewritten:
            await self.predict(vector, phase='first-drain-public-result')
        self.checkpoint('drained', dirty=0)
        self.checker.check(drain_begin + 4, len(self.checker.drains), phase='exact-four-drains-with-updated-payload')
        # These are real earlier cold lookups, not fabricated hit/valid masks.
        # Captured-cold feedback may reallocate after the first write has drained.
        reactivated = tuple(replace(vector, target=vector.target + 0x40, position=5) for vector in rewritten)
        await self.predict(vectors[-1], phase='restore-real-read-pressure')
        for vector, prediction in zip(reactivated, cold, strict=True):
            await self.submit(vector, prediction, phase='captured-cold-clean-reactivation')
        await ClockCycles(self.agent.dut.clock, 4)
        self.checkpoint('clean_reactivate', dirty=1)
        self.checker.check(4, sum(item['role'] == 'clean_changed' for item in self.checker.actions[action_begin:]), phase='four-actual-clean-reactivations')
        await self.agent.drain_bank_writes()
        for vector in reactivated:
            await self.predict(vector, phase='reactivated-complete-resident-profile')
        self.checker.check(drain_begin + 8, len(self.checker.drains), phase='exact-eight-drains-total')
        # Revisit in reverse order to make retained neighbors observable too.
        for vector in reversed(reactivated):
            await self.predict(vector, phase='reverse-retained-neighbor-revisit')
        self.completed_orders.append(self.order)
        self.case_windows.append(dict(window, end_tick=self.checker.last_tick,
                                      drain_end=len(self.checker.drains), action_end=len(self.checker.actions)))
