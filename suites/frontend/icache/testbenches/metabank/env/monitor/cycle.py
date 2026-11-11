"""Lossless complete MetaBank phase snapshots, distinct from valid-way checking."""
from dataclasses import dataclass
from toffee import Bundle, SamplingMonitor
from suites.frontend.icache.testbenches.metabank.transactions.types import MetaBankWay


@dataclass(frozen=True, slots=True)
class MetaFrame:
    reset: int
    read: tuple
    write: tuple
    flush: int
    bist: tuple
    controls: tuple
    read_ready: int
    write_ready: int
    entries: tuple[MetaBankWay, ...]
    bist_ack: int
    bist_outdata: int


class MetaCycleMonitor(SamplingMonitor):
    def __init__(self, trigger, dut, ports):
        self.active = False
        self.sample = Bundle(reset=dut.reset, read=ports.read.bits, write=ports.write.bits,
            flush=ports.flush_all.bits.flushAll, bist=ports.mbist.bits, controls=ports.sram_control.bits,
            read_ready=ports.read_ready.bits.ready, write_ready=ports.write_ready.bits.ready,
            entries=ports.response, mbist_response=ports.mbist_response.bits).compile_sampler()
        super().__init__(trigger, capture=self.capture_frame, delivery='lossless', capacity=64)

    def capture_frame(self, event):
        value = self.sample()
        return MetaFrame(value.reset.as_int(), (value.read.valid.as_int(), value.read.setIdx.as_int()),
            tuple(getattr(value.write, name).as_int() for name in
                  ('valid', 'setIdx', 'waymask', 'phyTag', 'maybeRvcMap', 'code')),
            value.flush.as_int(),
            tuple(getattr(value.bist, name).as_int() for name in
                  ('req', 'all', 'array', 'readen', 'writeen', 'be', 'addr', 'addr_rd', 'indata')),
            tuple(tuple(getattr(group, name).as_int() for name in
                ('hold', 'bypass', 'bp_clken', 'aux_clk', 'aux_ckbp', 'mcp_hold', 'cgen')) for group in value.controls.ways),
            value.read_ready.as_int(), value.write_ready.as_int(),
            tuple(MetaBankWay(entry.valid.as_int(), entry.bits.meta.phyTag.as_int(),
                entry.bits.meta.maybeRvcMap.as_int(), entry.bits.code.as_int()) for entry in value.entries),
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
