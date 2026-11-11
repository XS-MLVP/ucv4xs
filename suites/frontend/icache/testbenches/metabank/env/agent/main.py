"""MetaBank transactions with independent validity/storage ancestry and checks."""
from dataclasses import dataclass
from suites.frontend.icache.testbenches.shared.env.array_agent import ArrayAgent
from suites.frontend.icache.testbenches.metabank.env.bundle.ports import MetaBankPorts
from suites.frontend.icache.testbenches.metabank.env.bundle.abi import validate_binding
from suites.frontend.icache.testbenches.metabank.checker.transactions import MetaTransactions
from suites.frontend.icache.testbenches.metabank.env.driver.cycle import encode
from suites.frontend.icache.testbenches.metabank.model.bank import MetaEntry
from suites.frontend.icache.testbenches.metabank.model.bank import MetaWay
from suites.frontend.icache.testbenches.metabank.env.monitor.cycle import MetaCycleMonitor
from suites.frontend.icache.testbenches.metabank.transactions.types import MetaBankRead
from suites.frontend.icache.testbenches.metabank.transactions.types import MetaBankWrite
from suites.frontend.icache.testbenches.metabank.transactions.types import MetaBankWay
from suites.frontend.icache.testbenches.metabank.transactions.types import MetaBankCycle
from suites.frontend.icache.testbenches.metabank.transactions.types import MetaBankBist

RESET_MARGIN = 32
NUM_SETS, NUM_WAYS = 128, 4


@dataclass(frozen=True, slots=True)
class MetaGeometry:
    sets: int = NUM_SETS
    ways: int = NUM_WAYS


class MetaBankAgent(ArrayAgent):
    label = 'ICacheMetaBank'
    geometry = MetaGeometry()

    def __init__(self, dut, *, sets=NUM_SETS, ways=NUM_WAYS):
        if type(sets) is not int or type(ways) is not int or (sets, ways) != (128, 4):
            raise ValueError('current ICacheMetaBank adapter requires DefaultConfig 128 sets/four ways/two macros')
        ports = MetaBankPorts.bind(dut)
        validate_binding(ports, dut)
        super().__init__(dut, ports, MetaTransactions(), cycle_type=MetaBankCycle,
            encoder=encode, monitor_type=MetaCycleMonitor, control_groups=2,
            bindings=dict(read=ports.read, write=ports.write, flush=ports.flush_all, bist=ports.mbist),
            label='ICacheMetaBank')

    def read_entries(self):
        self._active()
        return tuple(MetaWay(way.valid, MetaEntry(way.phy_tag, way.maybe_rvc_map, way.code))
                     for way in self._latest.entries)

    async def write(self, set_index, waymask, *, phy_tag, maybe_rvc_map=0, code=0):
        request = MetaBankWrite(set_index, waymask, phy_tag, maybe_rvc_map, code)
        async with self._operation():
            await self.wait_for(lambda: self.write_ready(), what='write ready')
            offered = await self._cycle(MetaBankCycle(write=request))
            consumed = await self._cycle(MetaBankCycle())
            uid, = offered.launched
            self.checker.check('empty-write' if not request.waymask else 'written', self.checker._rows[uid].state, uid)
            self.checker.check(True, uid in consumed.accepted, uid)

    async def read(self, set_index):
        request = MetaBankRead(set_index)
        async with self._operation():
            await self.wait_for(lambda: self.read_ready(), what='read ready')
            offered = await self._cycle(MetaBankCycle(read=request))
            consumed = await self._cycle(MetaBankCycle())
            uid, = offered.launched
            self.checker.check((uid,), tuple(result.uid for result in consumed.responses), uid)
            entries = self.read_entries()
            self.checker.deliver(consumed.responses[0], tuple(MetaBankWay(way.valid, way.entry.phy_tag,
                way.entry.maybe_rvc_map, way.entry.code) for way in entries))
            return entries

    async def check_read(self, set_index):
        return await self.read(set_index)

    async def flush_all(self):
        async with self._operation():
            # Preserve the original two-level-edge flush schedule and release.
            await self._cycle(MetaBankCycle(flush_all=1))
            await self._cycle(MetaBankCycle(flush_all=1))
            await self._cycle(MetaBankCycle())

    async def bist_command(self, child='', *, array=0, all_arrays=0, readen=1,
                           writeen=0, be=0, addr=0, addr_rd=0, indata=0, hold=2):
        if type(child) is not str or child != '':
            raise ValueError('ICacheMetaBank exposes one MBIST pipeline, selected macros use array0/1')
        request = MetaBankBist(array, all_arrays, readen, writeen, be, addr, addr_rd, indata)
        if type(hold) is not int or hold <= 0:
            raise ValueError('ICacheMetaBank MBIST hold requires positive integer cycles')
        async with self._operation():
            await self.wait_for(lambda: self.write_ready(), what='MBIST initialization')
            first = None
            for _ in range(hold):
                offered = await self._cycle(MetaBankCycle(bist=request))
                if first is None:
                    first, = offered.launched
            for _ in range(4):
                await self._cycle(MetaBankCycle())
            self.checker.check(True, self.checker._rows[first].ack_tick is not None, first)
            return 1, self._latest.bist_outdata
