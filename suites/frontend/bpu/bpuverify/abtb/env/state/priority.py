"""bpuverify.abtb.env.state.priority components."""

from copy import deepcopy
from dataclasses import asdict
from bpuverify.common.env.trace import dump_trace
from toffee import ClockCycles
from bpuverify.abtb.transaction.types import AbtbTraining
from bpuverify.abtb.case.state.vectors import interior_set_vectors
from bpuverify.abtb.monitor.state.counter import CounterMonitor
from bpuverify.abtb.coverage.state.supplemental import transition_coverage
from bpuverify.abtb.model.state.counter import index
from bpuverify.abtb.model.state.counter import victim
from bpuverify.abtb.case.state.counter import packed
from bpuverify.abtb.checker.state.priority import PriorityChecker
from bpuverify.abtb.driver.state.training_driver import AcceptedPulseDriver
from bpuverify.abtb.env.state.session import StateObservation
from bpuverify.abtb.case.state.scope import bank_index
from bpuverify.abtb.case.state.scope import way_axis
from bpuverify.abtb.case.state.scope import physical_axis


class ResetPriorityScenario:
    def __init__(self, agent, output, *, bank, way, old, taken, release_phase, coverage=None):
        bank_index(bank)
        way_axis((way,))
        physical_axis((old,), size=4, name='counter prestate')
        physical_axis((taken,), size=2, name='taken bit')
        physical_axis((release_phase,), size=4, name='release phase')
        self.agent, self.output = agent, output
        self.bank, self.way, self.old = bank, way, old
        self.taken, self.release_phase = taken, release_phase
        self.coverage = coverage
        self.set_index = 5
        self.name = f'bank{bank}-way{way}-old{old}-taken{taken}-phase{release_phase}'
        self.checker = PriorityChecker(scope=self.name,
            coverage=transition_coverage(bank, (self.set_index,), capture=False))
        self.monitor = CounterMonitor(agent)
        self.known, self.intents, self.profiles = {}, [], []
        self.metadata_ticks = {}
        self.driver = AcceptedPulseDriver(agent.ports.training, checker=self.checker)
        self.observation = StateObservation(agent, self.monitor, self.checker, driver=self.driver)

    async def __aenter__(self):
        await self.observation.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.observation.__aexit__(exc_type, exc, traceback)
        report = dict(name=self.name, bank=self.bank, way=self.way, old=self.old,
            taken=self.taken, release_phase=self.release_phase, set_index=self.set_index,
            intents=self.intents, profiles=self.profiles, collisions=self.checker.collisions,
            records=[dict(row, cells=packed(row['cells'])) for row in self.checker.records],
            confirmed=self.checker.confirmed,
            failure=None if self.checker.failure is None and exc is None else repr(self.checker.failure or exc), trace_kind='abtb-reset-priority')
        if exc_type is None:
            report['summary'] = self.checker.summary()
        dump_trace((self.output / f'{self.name}.json'), report)

    async def predict(self, vector, *, phase):
        actual = await self.agent.predict(vector.pc, path_hash=self.bank)
        check = self.checker.check
        check((1, 1 << self.bank, self.set_index),
              (actual.meta['valid'], actual.meta['bankMask'], actual.meta['setIdx']),
              phase=phase + '.meta-route')
        expected = []
        for way, observed in enumerate(actual.entries):
            resident = self.known.get(way)
            matches = resident is not None and resident.pc == vector.pc
            valid = int(matches)
            check((valid, valid, valid), (observed.valid, actual.meta['entries'][way]['hit'],
                  actual.micro_tage['result'][way]['valid']), phase=phase + '.all-way-valid', way=way)
            if matches:
                value = self.checker.reference.cells[index(self.bank, self.set_index, way)]
                entry = dict(valid=1, taken=int(value >= 2), target=resident.target,
                             position=resident.position, branch_type=1, ras_action=0)
                check(entry, asdict(observed), phase=phase + '.full-entry', way=way)
                check(dict(taken=int(value >= 2), cfiPosition=resident.position,
                      attribute=dict(branchType=1, rasAction=0), isStrongBias=int(value in (0, 3))),
                      actual.micro_tage['result'][way]['bits'], phase=phase + '.strength', way=way)
                check((resident.position, resident.target & ((1 << 22) - 1), dict(branchType=1, rasAction=0)),
                      (actual.meta['entries'][way]['position'], actual.meta['entries'][way]['targetLowerBits'],
                       actual.meta['entries'][way]['attribute']), phase=phase + '.metadata-identity', way=way)
                expected.append(dict(way=way, counter=value, entry=entry))
        self.profiles.append(dict(phase=phase, pc=vector.pc, checked_tick=self.checker.last_tick,
                                  expected=expected, actual=asdict(actual)))
        self.metadata_ticks[id(actual)] = self.checker.last_tick
        return actual

    def submit(self, vector, prediction, *, taken, write=None, phase):
        transaction = AbtbTraining(pc=vector.pc, target=vector.target, taken=taken,
            position=vector.position, branch_type=1, meta=deepcopy(prediction.meta))
        self.checker.plan(transaction, write=write)
        self.intents.append(dict(after_tick=self.checker.last_tick, phase=phase,
                                 request=asdict(transaction), expected_write=write,
                                 metadata_tick=self.metadata_ticks[id(prediction)]))
        return self.driver.send(self.agent.encode_training(transaction))

    async def settled(self, vector, prediction, *, taken, write=None, phase):
        self.agent.lookup_driver.quiesce()
        handle = self.submit(vector, prediction, taken=taken, write=write, phase=phase)
        await handle
        await self.agent.drain_bank_writes()
        self.checker.raise_failure()

    async def run(self):
        vectors = interior_set_vectors(self.bank, self.set_index, count=5)
        for vector in vectors[:4]:
            cold = await self.predict(vector, phase='populate-cold')
            way = victim(self.checker.reference.plru[self.bank][self.set_index])
            write = dict(bank=self.bank, set_index=self.set_index, way=way, reset_counter=1)
            await self.settled(vector, cold, taken=1, write=write, phase='populate-allocation')
            self.known[way] = vector
            await self.predict(vector, phase='populate-visible')
        target = self.known[self.way]
        for _ in range(2 - self.old if self.old < 2 else int(self.old == 3)):
            prediction = await self.predict(target, phase='old-value-before')
            await self.settled(target, prediction, taken=int(self.old == 3), phase='set-old-value')
        for way in (self.way ^ 1, self.way ^ 2):
            vector = self.known[way]
            prediction = await self.predict(vector, phase='steer-before')
            await self.settled(vector, prediction, taken=1, phase='steer-independent-victim')
        self.checker.check(self.way, victim(self.checker.reference.plru[self.bank][self.set_index]),
                           phase='independent-victim-steered')
        old_prediction = await self.predict(target, phase='real-old-resident-metadata')
        self.checker.check(self.old, self.checker.reference.cells[index(self.bank, self.set_index, self.way)],
                           phase='independently-planned-counter-prestate')
        allocate = vectors[4]
        cold = await self.predict(allocate, phase='cold-under-read-pressure')
        write = dict(bank=self.bank, set_index=self.set_index, way=self.way, reset_counter=1)
        await self.submit(allocate, cold, taken=1, write=write, phase='queue-cold-under-real-reads')
        await ClockCycles(self.agent.dut.clock, 4)
        await self.predict(allocate, phase='allocation-still-not-visible')
        self.checker.check(1, len(self.checker.planned_writes), phase='write-really-queued')
        handle = self.submit(target, old_prediction, taken=self.taken, phase='feedback-overlaps-queued-reset')
        # Phase 0 releases read pressure one cycle BEFORE pulse completion.
        # Waiting for pulse completion would only test the later T2 PLRU port.
        await ClockCycles(self.agent.dut.clock, self.release_phase + 1)
        await self.agent.drain_bank_writes()
        accepted = await handle
        self.checker.check(handle.accepted_event.tick, accepted.tick, phase='actual-acceptance-event-returned')
        self.checker.raise_failure()
        self.known[self.way] = allocate
        for vector in vectors:
            await self.predict(vector, phase='post-overlap-full-profile')
        for collision in self.checker.collisions:
            self.checker.check((self.bank, self.set_index, self.way, self.old, 2),
                (collision['bank'], collision['set_index'], collision['way'], collision['before'], collision['actual']),
                phase='qualified-same-cell-priority-result')
            if self.coverage is not None:
                self.coverage.sample({name: collision[name] for name in ('bank', 'way', 'before', 'operation')})
        return len(self.checker.collisions)
