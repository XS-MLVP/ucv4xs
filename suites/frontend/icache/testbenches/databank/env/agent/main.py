"""DataBank domain API over shared SDK-owned, continuously checked execution."""
from dataclasses import dataclass
from suites.frontend.icache.testbenches.shared.env.array_agent import ArrayAgent
from suites.frontend.icache.testbenches.databank.env.bundle.ports import DataBankPorts
from suites.frontend.icache.testbenches.databank.env.bundle.abi import validate_binding
from suites.frontend.icache.testbenches.databank.checker.transactions import BankTransactions
from suites.frontend.icache.testbenches.databank.env.driver.cycle import encode
from suites.frontend.icache.testbenches.databank.model.bank import DataEntry
from suites.frontend.icache.testbenches.databank.env.monitor.cycle import BankCycleMonitor
from suites.frontend.icache.testbenches.databank.transactions.types import BankBist
from suites.frontend.icache.testbenches.databank.transactions.types import BankCycle
from suites.frontend.icache.testbenches.databank.transactions.types import BankPortRead
from suites.frontend.icache.testbenches.databank.transactions.types import BankRead
from suites.frontend.icache.testbenches.databank.transactions.types import BankReadData
from suites.frontend.icache.testbenches.databank.transactions.types import BankWrite

RESET_MARGIN = 32
NUM_SETS, NUM_WAYS = 256, 4


@dataclass(frozen=True, slots=True)
class BankGeometry:
    sets: int = NUM_SETS
    ways: int = NUM_WAYS


class DataBankAgent(ArrayAgent):
    label = 'ICacheDataBank'
    geometry = BankGeometry()

    def __init__(self, dut, *, sets=NUM_SETS, ways=NUM_WAYS):
        if type(sets) is not int or type(ways) is not int or (sets, ways) != (NUM_SETS, NUM_WAYS):
            raise ValueError('current ICacheDataBank adapter requires DefaultConfig 256 sets and four ways')
        ports = DataBankPorts.bind(dut)
        validate_binding(ports, dut)
        super().__init__(dut, ports, BankTransactions(), cycle_type=BankCycle,
            encoder=encode, monitor_type=BankCycleMonitor, control_groups=4,
            bindings=dict(read=ports.read, write=ports.write, bist=ports.mbist), label='ICacheDataBank')

    def read_entries(self):
        """Non-consuming immutable monitor view, never a fresh native sample."""
        self._active()
        return tuple(DataEntry(data, code) for data, code in
                     zip(self._latest.entries.data, self._latest.entries.code, strict=True))

    async def write(self, set_index, waymask, *, data, code=0):
        transaction = BankWrite(set_index, waymask, data, code)
        async with self._operation():
            await self.wait_for(lambda: self.write_ready(), what='write ready')
            offered = await self._cycle(BankCycle(write=transaction))
            consumed = await self._cycle(BankCycle())
            uid, = offered.launched
            self.checker.check('empty-write' if not waymask else 'written',
                               self.checker._rows[uid].state, uid)
            self.checker.check(True, uid in consumed.accepted, uid)

    async def read(self, set_index):
        request = BankRead(set_index)
        async with self._operation():
            await self.wait_for(lambda: self.read_ready(), what='read ready')
            offered = await self._cycle(BankCycle(read=BankPortRead((request.set_index,) * 4)))
            consumed = await self._cycle(BankCycle())
            uid, = offered.launched
            self.checker.check((uid,), tuple(result.uid for result in consumed.responses), uid)
            entries = self.read_entries()
            value = BankReadData(tuple(entry.data for entry in entries), tuple(entry.code for entry in entries))
            self.checker.deliver(consumed.responses[0], value)
            return entries

    async def check_read(self, set_index):
        return await self.read(set_index)

    async def bist_command(self, *, array=0, all_arrays=0, readen=1, writeen=0,
                           be=0, addr=0, addr_rd=0, indata=0, hold=2):
        request = BankBist(array, all_arrays, readen, writeen, be, addr, addr_rd, indata)
        if type(hold) is not int or hold <= 0:
            raise ValueError('ICacheDataBank MBIST hold requires positive integer cycles')
        async with self._operation():
            await self.wait_for(lambda: self.write_ready(), what='MBIST initialization')
            first = None
            for _ in range(hold):
                offered = await self._cycle(BankCycle(bist=request))
                if first is None:
                    first, = offered.launched
            for _ in range(4):
                await self._cycle(BankCycle())
            self.checker.check(True, self.checker._rows[first].ack_tick is not None, first)
            return 1, self._latest.bist_outdata
