"""suites.frontend.bpu.abtb.env.state.replacer components."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage

from suites.frontend.bpu.runtime.artifacts import output_path
from dataclasses import asdict
from dataclasses import replace
from suites.frontend.bpu.runtime.trace import dump_trace
from toffee import CheckContext
from toffee import ClockCycles
from toffee import ScoreboardMode
from suites.frontend.bpu.abtb.transaction.types import AbtbTraining
from suites.frontend.bpu.abtb.case.state.vectors import interior_set_vectors
from suites.frontend.bpu.abtb.model.state.replacer import route
from suites.frontend.bpu.abtb.model.state.replacer import touch
from suites.frontend.bpu.abtb.model.state.replacer import victim
from suites.frontend.bpu.abtb.checker.state.replacer import ReplacerChecker
from suites.frontend.bpu.abtb.monitor.state.replacer import ReplacerMonitor
from suites.frontend.bpu.abtb.env.state.session import StateObservation
from suites.frontend.bpu.abtb.coverage.state.supplemental import replacer_coverage
from suites.frontend.bpu.abtb.case.state.scope import bank_index
from suites.frontend.bpu.abtb.case.state.scope import set_axis
from suites.frontend.bpu.abtb.case.state.scope import way_axis
from toffee import CoverageDatabase
from suites.frontend.bpu.abtb.case.state.replacer import compact


class ReplacerScenario:
    def __init__(self, agent, output, *, bank, same_set, sets=range(64), victims=range(4)):
        bank_index(bank)
        sets, victims = set_axis(sets), way_axis(victims)
        if type(same_set) is not bool:
            raise ValueError('same_set must be bool')
        self.agent, self.output = agent, output
        self.bank, self.same_set = bank, same_set
        self.checker = ReplacerChecker(scope=f'full-grid-bank{bank}-same{same_set}')
        self.monitor = ReplacerMonitor(agent)
        self.observation = StateObservation(agent, self.monitor, self.checker)
        self.coverage = replacer_coverage(bank, same_set, sets=tuple(sets), victims=tuple(victims))
        self.profiles = []
        self.metadata_ticks = {}
        self.known = {(b, s): {} for b in range(4) for s in range(64)}
        self.cases = []
        self.intents = []

    def check(self, expected, actual, **request):
        self.checker.raise_failure()
        self.checker.scoreboard.check(expected=expected, actual=actual,
            context=CheckContext(scoreboard=self.checker.scoreboard.name,
                mode=ScoreboardMode.DIRECT, sequence_id=len(self.cases),
                request=dict(bank=self.bank, same_set=self.same_set,
                    observed_tick=self.checker.last_tick, **request)))

    async def __aenter__(self):
        await self.observation.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.observation.__aexit__(exc_type, exc, traceback)
        name = f'b{self.bank}-same{self.same_set}'
        report = dict(bank=self.bank, same_set=self.same_set, cases=self.cases,
            intents=self.intents, initialized_from_real_reset=True,
            cycles=len(self.checker.records), checks=asdict(self.checker.scoreboard.status),
            failure=None if self.checker.failure is None and exc is None else repr(self.checker.failure or exc),
            state_encoding='64 independent three-bit PLRU states, set0 at bits2:0',
            records=[compact(row) for row in self.checker.records], profiles=self.profiles,
            trace_kind='abtb-replacer-state')
        dump_trace((self.output / f'matrix-{name}.json'), report)
        write_functional_coverage(CoverageDatabase([self.coverage]), output_path(self.output / f'functional-coverage-replacer-{name}.json'))
        if exc_type is None:
            self.checker.raise_failure()

    async def predict(self, vector, *, bank=None):
        bank = self.bank if bank is None else bank
        expected_bank, expected_set = route(vector.pc, bank)
        self.check(bank, expected_bank, phase='independent-public-address-decode')
        actual = await self.agent.predict(vector.pc, path_hash=bank)
        self.check((1 << bank, expected_set),
                   (actual.meta['bankMask'], actual.meta['setIdx']),
                   phase='public-metadata-address', pc=vector.pc)
        residents = self.known[(bank, expected_set)]
        wanted = {way: item for way, item in residents.items() if item.pc == vector.pc}
        expected = tuple((1, item.position, item.branch_type, 0, item.target)
                         if (item := wanted.get(way)) is not None else (0, None, None, None, None)
                         for way in range(4))
        observed = tuple((1, item.position, item.branch_type, item.ras_action, item.target)
                         if item.valid else (0, None, None, None, None) for item in actual.entries)
        self.check(expected, observed, phase='complete-public-resident-profile', pc=vector.pc)
        for way in wanted:
            self.check(1, actual.entries[way].taken, phase='public-direction-holds', pc=vector.pc, way=way)
        self.profiles.append(dict(checked_tick=self.checker.last_tick, bank=bank,
            set_index=expected_set, pc=vector.pc, actual=asdict(actual),
            residents={way: asdict(value) for way,value in residents.items()}))
        self.metadata_ticks[id(actual)] = self.checker.last_tick
        return actual

    def training(self, vector, prediction):
        result = AbtbTraining(pc=vector.pc, target=vector.target, taken=1,
            position=vector.position, branch_type=vector.branch_type, meta=prediction.meta)
        self.intents.append(dict(after_tick=self.checker.last_tick,
            request=asdict(result), metadata_tick=self.metadata_ticks[id(prediction)]))
        return result

    async def allocate(self, vector):
        prediction = await self.predict(vector)
        self.check(False, any(entry.valid for entry in prediction.entries),
                   phase='real-cold-metadata', pc=vector.pc)
        b, s = route(vector.pc, self.bank)
        way = victim(self.checker.expected[b][s])
        await self.agent.train(self.training(vector, prediction))
        self.known[(b, s)][way] = vector
        actual = await self.predict(vector)
        self.check(1, actual.entries[way].valid,
                   phase='allocation-victim-independent-reference', way=way, pc=vector.pc)
        return actual, way

    async def case(self, *, set_index, victim_way, epoch):
        vectors = tuple(replace(vector,
            pc=vector.pc + epoch * 8 * 512,
            target=0x40100000 + epoch * 256 + self.bank * 64 + index * 8)
            for index, vector in enumerate(interior_set_vectors(self.bank, set_index, count=6)))
        self.check((self.bank, set_index), route(vectors[0].pc, self.bank),
                   phase='case-address', epoch=epoch)
        for vector in vectors[:4]:
            await self.allocate(vector)
        residents = self.known[(self.bank, set_index)]
        self.check(set(range(4)), set(residents), phase='four-independent-resident-ways')

        if not self.same_set:
            neighbor = (set_index + 1) % 64
            neighbor_vectors = tuple(replace(vector,
                pc=vector.pc + epoch * 8 * 512,
                target=0x40300000 + epoch * 256 + self.bank * 64 + index * 8)
                for index, vector in enumerate(interior_set_vectors(self.bank, neighbor, count=4)))
            for vector in neighbor_vectors:
                await self.allocate(vector)
            neighbor_before = self.checker.expected[self.bank][neighbor]
            neighbor_way = victim(neighbor_before)
            neighbor_vector = self.known[(self.bank, neighbor)][neighbor_way]
            self.check(False, neighbor_before == touch(neighbor_before, neighbor_way),
                       phase='different-set-read-is-not-an-idempotent-touch')

        # Set the replacement candidate by independent touches, not by reading
        # the hardware's victim or selecting a lucky observed allocation.
        for way in (victim_way ^ 1, victim_way ^ 2):
            vector = residents[way]
            prediction = await self.predict(vector)
            await self.agent.train(self.training(vector, prediction))
        before = self.checker.expected[self.bank][set_index]
        self.check(victim_way, victim(before), phase='steered-independent-victim')

        if self.same_set:
            other_pair = 1 - (victim_way >> 1)
            hit_way = (other_pair << 1) | ((before >> other_pair) & 1)
            hit_vector = residents[hit_way]
            hit_prediction = await self.predict(hit_vector)
            self.check(False, touch(before, victim_way) == touch(touch(before, hit_way), victim_way),
                       phase='priority-witness-discriminates-sequential-merge')
        else:
            hit_vector, hit_way = neighbor_vector, neighbor_way
            hit_prediction = await self.predict(hit_vector)

        allocate = vectors[4]
        cold = await self.predict(allocate)
        self.check(False, any(entry.valid for entry in cold.entries), phase='buffered-allocation-cold')
        await self.agent.train_under_read_pressure(self.training(allocate, cold))
        await ClockCycles(self.agent.dut.clock, 4)
        pending = await self.predict(allocate)
        self.check(False, any(entry.valid for entry in pending.entries), phase='write-really-blocked-by-reads')
        begin_tick = self.checker.last_tick
        await self.agent.train_under_read_pressure(self.training(hit_vector, hit_prediction))
        await self.agent.drain_bank_writes()
        self.checker.raise_failure()
        conflicts = [row for row in self.checker.conflicts(bank=self.bank, same_set=self.same_set)
                     if row['tick'] > begin_tick]
        self.check(1, len(conflicts), phase='qualified-actual-simultaneous-port-event',
                   set_index=set_index, victim_way=victim_way)
        conflict = conflicts[0]
        self.check((set_index, victim_way, set_index if self.same_set else (set_index + 1) % 64,
                    tuple(int(w == hit_way) for w in range(4))),
                   (conflict['write_set'], conflict['write_way'], conflict['read_set'], conflict['read_mask']),
                   phase='actual-port-event-matches-public-intent', set_index=set_index)
        expected_after = touch(before, victim_way)
        self.check(expected_after, self.checker.expected[self.bank][set_index],
                   phase='same-set-write-only-or-different-set-independent-state')
        if not self.same_set:
            self.check(touch(neighbor_before, hit_way), self.checker.expected[self.bank][neighbor],
                       phase='different-set-read-update-is-retained')
        self.known[(self.bank, set_index)][victim_way] = allocate
        for vector in vectors[:5]:
            await self.predict(vector)
        if not self.same_set:
            await self.predict(hit_vector)

        # A new public allocation must use the priority-selected state. The
        # first queued allocation chose its victim BEFORE the conflict, so it
        # alone would not prove this externally visible consequence.
        next_expected = victim(expected_after)
        _, next_actual = await self.allocate(vectors[5])
        self.check(next_expected, next_actual, phase='post-conflict-public-replacement')
        for vector in vectors:
            await self.predict(vector)
        if not self.same_set:
            for vector in tuple(self.known[(self.bank, (set_index + 1) % 64)].values()):
                await self.predict(vector)
        result = dict(bank=self.bank, set_index=set_index, victim_way=victim_way,
            same_set=self.same_set, epoch=epoch, conflict_tick=conflict['tick'],
            hit_way=hit_way, independent_state_before=before, independent_state_after=expected_after,
            next_expected_victim=next_expected, actual_next_victim=next_actual,
            public_profiles_checked=True, exact_simultaneous_event=True,
            read_set=conflict['read_set'], write_set=conflict['write_set'])
        if not self.same_set:
            result.update(independent_neighbor_before=neighbor_before,
                          independent_neighbor_after=touch(neighbor_before, hit_way))
        self.cases.append(result)
        self.coverage.sample(dict(bank=self.bank, set_index=set_index,
            victim_way=victim_way, relation='same_set' if self.same_set else 'different_set'))

    async def scrub(self):
        # Complete retained-profile revisit, including otherwise idle banks.
        resident = 0
        for (bank, _), ways in self.known.items():
            for vector in tuple(ways.values()):
                await self.predict(vector, bank=bank)
                resident += 1
        for set_index in range(64):
            vector = interior_set_vectors(self.bank, set_index, count=1)[0]
            for other_bank in range(4):
                if other_bank != self.bank:
                    await self.predict(vector, bank=other_bank)
        return resident
