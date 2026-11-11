"""Native binding for the InstrUncache top level (TL A/D + IFU + WFI)."""

from __future__ import annotations

from toffee import Bundle

from suites.frontend.instr_uncache.testbenches.instr_uncache.model import Inputs
from suites.frontend.instr_uncache.testbenches.instr_uncache.model import Outputs


INPUTS = {
    "reset": ("reset", 1),
    "a_ready": ("auto_client_out_a_ready", 1),
    "d_valid": ("auto_client_out_d_valid", 1),
    "d_source": ("auto_client_out_d_bits_source", 1),
    "d_data": ("auto_client_out_d_bits_data", 64),
    "d_corrupt": ("auto_client_out_d_bits_corrupt", 1),
    "d_denied": ("auto_client_out_d_bits_denied", 1),
    "req_valid": ("io_fromIfu_req_valid", 1),
    "req_addr": ("io_fromIfu_req_bits_addr_addr", 47),
    "req_mem_back_mm": ("io_fromIfu_req_bits_memBackTypeMM", 1),
    "req_mem_page_nc": ("io_fromIfu_req_bits_memPageTypeNC", 1),
    "wfi_req": ("io_wfi_wfiReq", 1),
}

OUTPUTS = {
    "req_ready": ("io_fromIfu_req_ready", 1),
    "a_valid": ("auto_client_out_a_valid", 1),
    "a_addr": ("auto_client_out_a_bits_address", 48),
    "a_mem_page_nc": ("auto_client_out_a_bits_user_memPageType_NC", 1),
    "a_mem_back_mm": ("auto_client_out_a_bits_user_memBackType_MM", 1),
    "resp_valid": ("io_toIfu_resp_valid", 1),
    "resp_data": ("io_toIfu_resp_bits_data", 32),
    "resp_corrupt": ("io_toIfu_resp_bits_corrupt", 1),
    "resp_denied": ("io_toIfu_resp_bits_denied", 1),
    "resp_need_resend": ("io_toIfu_resp_bits_needResend", 1),
    "wfi_safe": ("io_wfi_wfiSafe", 1),
}

ABSENT = {
    "io_flush": "FrontendInlinedImp ties instrUncache.io.flush := false.B "
                "(Frontend.scala:266)",
    "auto_client_out_d_ready": "InstrUncacheImp overrides mmioGrant.ready := true.B "
                               "(InstrUncacheImp.scala:88)",
    "io_toIfu_resp_ready": "IfuUncacheUnit ties fromUncache.ready := true.B "
                           "(IfuUncacheUnit.scala:133)",
    "auto_client_out_a_bits_opcode": "edge.Get() fixes the Get opcode",
    "auto_client_out_a_bits_size": "edge.Get(..., lgSize=3) fixes the 8B size",
    "auto_client_out_a_bits_source": "the single client source is zero",
    "auto_client_out_a_bits_mask": "an 8B-aligned Get has mask 0xFF",
    "auto_client_out_a_bits_param": "Get fixes param=0",
    "auto_client_out_a_bits_corrupt": "Get fixes corrupt=0",
    "auto_client_out_b_ready": "B channel is tied inactive by the top",
    "auto_client_out_c_valid": "C channel is tied inactive by the top",
    "auto_client_out_e_valid": "E channel is tied inactive by the top",
}

INTERFACE = {
    "top": "InstrUncache",
    "inputs": {name: (width, port) for name, (port, width) in INPUTS.items()},
    "outputs": {name: (width, port) for name, (port, width) in OUTPUTS.items()},
    "absent": dict(ABSENT),
}


class TopPorts:
    response_ready = True
    d_ready = True

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
            raise ValueError(f"InstrUncache input ownership mismatch: "
                             f"{actual_inputs ^ expected_inputs}")
        actual_outputs = {
            name for name, signal in vars(dut).items()
            if name not in {"dut", "clock"} and callable(getattr(signal, "IsOutIO", None))
            and signal.IsOutIO()
        }
        expected_outputs = {name for name, _ in OUTPUTS.values()}
        if actual_outputs != expected_outputs:
            raise ValueError(f"InstrUncache output ownership mismatch: "
                             f"{actual_outputs ^ expected_outputs}")

    @staticmethod
    def encode(inputs: Inputs) -> dict[str, int]:
        if not isinstance(inputs, Inputs):
            raise TypeError("InstrUncache top driver requires semantic Inputs")
        values = {
            "reset": inputs.reset,
            "a_ready": inputs.a_ready,
            "d_valid": inputs.d_valid,
            "d_source": inputs.d_source,
            "d_data": inputs.d_data,
            "d_corrupt": inputs.d_corrupt,
            "d_denied": inputs.d_denied,
            "req_valid": inputs.req_valid,
            "req_addr": inputs.req_addr >> 1,
            "req_mem_back_mm": inputs.req_mem_back_mm,
            "req_mem_page_nc": inputs.req_mem_page_nc,
            "wfi_req": inputs.wfi_req,
        }
        if values.keys() != set(INPUTS):
            raise ValueError("InstrUncache encoder must drive every owned input once")
        return values

    def capture(self, event) -> Outputs:
        values = {field: int(value) for field, value in self._outputs.sample().items()}
        return Outputs(**values)
