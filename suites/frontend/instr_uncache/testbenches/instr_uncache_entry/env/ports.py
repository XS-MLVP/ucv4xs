"""Native binding and semantic encoding for InstrUncacheEntry.

Every generated input and output port is bound with an exact width and
direction.  Ports that the closure proved constant are listed with the Scala
fact that justifies their absence; if one reappears the binding fails and the
suite must migrate explicitly instead of silently driving an invented pin.
"""

from __future__ import annotations

from toffee import Bundle

from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import Inputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import Outputs


INPUTS = {
    "reset": ("reset", 1),
    "req_valid": ("io_req_valid", 1),
    "req_addr": ("io_req_bits_addr_addr", 47),
    "req_mem_back_mm": ("io_req_bits_memBackTypeMM", 1),
    "req_mem_page_nc": ("io_req_bits_memPageTypeNC", 1),
    "acquire_ready": ("io_mmioAcquire_ready", 1),
    "grant_valid": ("io_mmioGrant_valid", 1),
    "grant_data": ("io_mmioGrant_bits_data", 64),
    "grant_corrupt": ("io_mmioGrant_bits_corrupt", 1),
    "grant_denied": ("io_mmioGrant_bits_denied", 1),
    "wfi_req": ("io_wfi_wfiReq", 1),
}

OUTPUTS = {
    "req_ready": ("io_req_ready", 1),
    "resp_valid": ("io_resp_valid", 1),
    "resp_data": ("io_resp_bits_data", 32),
    "resp_corrupt": ("io_resp_bits_corrupt", 1),
    "resp_denied": ("io_resp_bits_denied", 1),
    "resp_need_resend": ("io_resp_bits_needResend", 1),
    "acquire_valid": ("io_mmioAcquire_valid", 1),
    "acquire_addr": ("io_mmioAcquire_bits_address", 48),
    "acquire_mem_page_nc": ("io_mmioAcquire_bits_user_memPageType_NC", 1),
    "acquire_mem_back_mm": ("io_mmioAcquire_bits_user_memBackType_MM", 1),
    "wfi_safe": ("io_wfi_wfiSafe", 1),
}

#: Absent generated ports and the contract fact that makes them constant.
ABSENT = {
    "io_flush": "FrontendInlinedImp ties instrUncache.io.flush := false.B "
                "(Frontend.scala:266); firtool prunes the port and needFlush",
    "io_id": "nMmioEntry == 1 makes the entry id constant zero",
    "io_mmioGrant_ready": "InstrUncacheImp overrides mmioGrant.ready := true.B "
                          "(InstrUncacheImp.scala:88)",
    "io_resp_ready": "IfuUncacheUnit ties fromUncache.ready := true.B "
                     "(IfuUncacheUnit.scala:133)",
    "io_mmioAcquire_bits_opcode": "edge.Get() fixes the Get opcode",
    "io_mmioAcquire_bits_size": "edge.Get(..., lgSize=3) fixes the 8B size",
    "io_mmioAcquire_bits_source": "the single client source is zero",
    "io_mmioAcquire_bits_mask": "an 8B-aligned Get has mask 0xFF",
}

INTERFACE = {
    "top": "InstrUncacheEntry",
    "inputs": {name: (width, port) for name, (port, width) in INPUTS.items()},
    "outputs": {name: (width, port) for name, (port, width) in OUTPUTS.items()},
    "absent": dict(ABSENT),
}


class EntryPorts:
    response_ready = True
    grant_ready = True

    def __init__(self, dut):
        def bind(name, width, *, output=False):
            signal = getattr(dut, name)
            if max(1, int(signal.mWidth)) != width:
                raise ValueError(f"{name}: expected native width {width}, got {signal.mWidth}")
            if ((output and not signal.IsOutIO())
                    or (not output and (not signal.IsInIO() or signal.IsOutIO()))):
                raise ValueError(f"{name}: wrong native port direction")
            return signal

        self.bits = Bundle(**{field: bind(name, width)
                              for field, (name, width) in INPUTS.items()})
        self._outputs = Bundle(**{field: bind(name, width, output=True)
                                  for field, (name, width) in OUTPUTS.items()})
        bind("clock", 1)
        for name, reason in ABSENT.items():
            if hasattr(dut, name):
                raise ValueError(f"{name} is present although the closure proved it constant "
                                 f"({reason}); migrate the binding explicitly")
        actual_inputs = {
            name for name, signal in vars(dut).items()
            if name not in {"dut", "clock"} and callable(getattr(signal, "IsInIO", None))
            and signal.IsInIO() and not signal.IsOutIO()
        }
        expected_inputs = {name for name, _ in INPUTS.values()}
        if actual_inputs != expected_inputs:
            raise ValueError(f"InstrUncacheEntry input ownership mismatch: "
                             f"{actual_inputs ^ expected_inputs}")
        actual_outputs = {
            name for name, signal in vars(dut).items()
            if name not in {"dut", "clock"} and callable(getattr(signal, "IsOutIO", None))
            and signal.IsOutIO()
        }
        expected_outputs = {name for name, _ in OUTPUTS.values()}
        if actual_outputs != expected_outputs:
            raise ValueError(f"InstrUncacheEntry output ownership mismatch: "
                             f"{actual_outputs ^ expected_outputs}")

    @staticmethod
    def encode(inputs: Inputs) -> dict[str, int]:
        if not isinstance(inputs, Inputs):
            raise TypeError("InstrUncacheEntry driver requires semantic Inputs")
        values = {
            "reset": inputs.reset,
            "req_valid": inputs.req_valid,
            "req_addr": inputs.req_addr >> 1,
            "req_mem_back_mm": inputs.req_mem_back_mm,
            "req_mem_page_nc": inputs.req_mem_page_nc,
            "acquire_ready": inputs.acquire_ready,
            "grant_valid": inputs.grant_valid,
            "grant_data": inputs.grant_data,
            "grant_corrupt": inputs.grant_corrupt,
            "grant_denied": inputs.grant_denied,
            "wfi_req": inputs.wfi_req,
        }
        if values.keys() != set(INPUTS):
            raise ValueError("InstrUncacheEntry encoder must drive every owned input once")
        return values

    def capture(self, event) -> Outputs:
        values = {field: int(value) for field, value in self._outputs.sample().items()}
        return Outputs(**values)

    @staticmethod
    def idle() -> Inputs:
        return Inputs()
