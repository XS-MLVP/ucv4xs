"""SDK lossless dual-phase full snapshots. No live signal survives capture."""
from dataclasses import dataclass
from toffee import Bundle, SamplingMonitor
from suites.frontend.icache.databank.transaction.types import BankReadData


@dataclass(frozen=True, slots=True)
class BankFrame:
    reset: int
    read: tuple
    write: tuple
    bist: tuple
    controls: tuple
    read_ready: int
    write_ready: int
    entries: BankReadData
    bist_ack: int
    bist_outdata: int


class BankCycleMonitor(SamplingMonitor):
    def __init__(self, trigger, dut, ports):
        self.active = False
        self.sample = Bundle(reset=dut.reset, read=ports.read.bits, write=ports.write.bits,
            bist=ports.mbist.bits, controls=ports.sram_control.bits,
            read_ready=ports.read_ready.bits.ready, write_ready=ports.write_ready.bits.ready,
            entries=ports.response, mbist_response=ports.mbist_response.bits).compile_sampler()
        super().__init__(trigger, capture=self.capture_frame, delivery='lossless', capacity=64)

    def capture_frame(self, event):
        value = self.sample()
        return BankFrame(value.reset.as_int(),
            (value.read.valid.as_int(), tuple(index.as_int() for index in value.read.setIdx),
             value.read.waymask.as_int()),
            tuple(getattr(value.write, name).as_int() for name in ('valid', 'setIdx', 'waymask', 'data', 'code')),
            tuple(getattr(value.bist, name).as_int() for name in
                  ('req', 'all', 'array', 'readen', 'writeen', 'be', 'addr', 'addr_rd', 'indata')),
            tuple(tuple(getattr(way, name).as_int() for name in
                ('hold', 'bypass', 'bp_clken', 'aux_clk', 'aux_ckbp', 'mcp_hold', 'cgen'))
                for way in value.controls.ways),
            value.read_ready.as_int(), value.write_ready.as_int(),
            BankReadData(tuple(entry.data.as_int() for entry in value.entries),
                         tuple(entry.code.as_int() for entry in value.entries)),
            value.mbist_response.ack.as_int(), value.mbist_response.outdata.as_int())

    def start(self, execution):
        super().start(execution)
        self.active = True
        return self

    async def aclose(self):
        try:
            await super().aclose()
        finally:
            self.active = False
