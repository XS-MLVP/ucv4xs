"""Native binding, encoding and capture for the IBuffer top DUT.

The generated IBuffer has 36 enqueue lanes, eight decode output lanes and the
backend walk/commit port.  Every generated input and output is bound with an
exact width and direction so a pruned or newly exported port fails loudly.
Performance counters are bound but are not part of the functional comparison;
that boundary is recorded in ``docs/spec/verification/exit-criteria.md``.
"""

from __future__ import annotations

from toffee import Bundle

from suites.frontend.ibuffer.testbenches.ibuffer.model import DECODE_WIDTH
from suites.frontend.ibuffer.testbenches.ibuffer.model import ENQUEUE_WIDTH
from suites.frontend.ibuffer.testbenches.ibuffer.model import LaneOutputs
from suites.frontend.ibuffer.testbenches.ibuffer.model import Outputs
from suites.frontend.ibuffer.testbenches.ibuffer.model import Inputs
from suites.frontend.ibuffer.testbenches.vtype_gen.model import VType

FIELDS = ("illegal", "vma", "vta", "vsew", "vlmul")
WIDTHS = {"illegal": 1, "vma": 1, "vta": 1, "vsew": 3, "vlmul": 3}

INPUTS: dict[str, tuple[str, int]] = {
    "reset": ("reset", 1),
    "in_valid": ("io_in_valid", 1),
    "valid": ("io_in_bits_valid", ENQUEUE_WIDTH),
    "enq_enable": ("io_in_bits_enqEnable", ENQUEUE_WIDTH),
    "exception_type": ("io_in_bits_exceptionType_value", 3),
    "is_backend_exception": ("io_in_bits_isBackendException", 1),
    "has_satp_flush": ("io_in_bits_hasSatpFlush", 1),
    "exception_cross_page": ("io_in_bits_exceptionCrossPage", 1),
    "exception_mask": ("io_in_bits_exceptionMask", ENQUEUE_WIDTH),
    "prev_instr_count": ("io_in_bits_prevInstrCount", 6),
    "flush": ("io_flush", 1),
    "decode_can_accept": ("io_fromBackend_decodeCanAccept", 1),
    "resuming_vtype": ("io_fromBackend_resumingVType", 1),
    "walk_to_arch_vtype": ("io_fromBackend_walkToArchVType", 1),
    "walk_vtype_valid": ("io_fromBackend_walkVType_valid", 1),
    "vsetvl_vtype_illegal": ("io_fromBackend_vsetvlVType_illegal", 1),
    "vsetvl_vtype_vma": ("io_fromBackend_vsetvlVType_vma", 1),
    "vsetvl_vtype_vta": ("io_fromBackend_vsetvlVType_vta", 1),
    "vsetvl_vtype_vsew": ("io_fromBackend_vsetvlVType_vsew", 3),
    "vsetvl_vtype_vlmul": ("io_fromBackend_vsetvlVType_vlmul", 3),
    "commit_vtype_valid": ("io_fromBackend_commitVType_vtype_valid", 1),
    "commit_vtype_illegal": ("io_fromBackend_commitVType_vtype_bits_illegal", 1),
    "commit_vtype_vma": ("io_fromBackend_commitVType_vtype_bits_vma", 1),
    "commit_vtype_vta": ("io_fromBackend_commitVType_vtype_bits_vta", 1),
    "commit_vtype_vsew": ("io_fromBackend_commitVType_vtype_bits_vsew", 3),
    "commit_vtype_vlmul": ("io_fromBackend_commitVType_vtype_bits_vlmul", 3),
    "commit_has_vsetvl": ("io_fromBackend_commitVType_hasVsetvl", 1),
    "backend_redirect": ("io_backendRedirectTopdown_backendRedirect", 1),
    "control_flow_redirect": ("io_backendRedirectTopdown_controlFlowRedirect", 1),
    "memory_violation_redirect": (
        "io_backendRedirectTopdown_memoryViolationRedirect", 1),
    "tage_miss_bubble": ("io_backendRedirectTopdown_tageMissBubble", 1),
    "ittage_miss_bubble": ("io_backendRedirectTopdown_ittageMissBubble", 1),
    "ras_miss_bubble": ("io_backendRedirectTopdown_rasMissBubble", 1),
}
for _lane in range(ENQUEUE_WIDTH):
    INPUTS[f"instr_{_lane}"] = (f"io_in_bits_instrs_{_lane}", 32)
    INPUTS[f"is_rvc_{_lane}"] = (f"io_in_bits_isRvc_{_lane}", 1)
    INPUTS[f"foldpc_{_lane}"] = (f"io_in_bits_foldpc_{_lane}", 10)
    if _lane < ENQUEUE_WIDTH - 1:
        # The IFU drives lane 35's predTaken as a constant; the port is pruned.
        INPUTS[f"pred_taken_{_lane}"] = (
            f"io_in_bits_instrEndOffset_{_lane}_predTaken", 1)
    INPUTS[f"offset_{_lane}"] = (f"io_in_bits_instrEndOffset_{_lane}_offset", 5)
    INPUTS[f"ftq_flag_{_lane}"] = (f"io_in_bits_ftqPtr_{_lane}_flag", 1)
    INPUTS[f"ftq_value_{_lane}"] = (f"io_in_bits_ftqPtr_{_lane}_value", 6)
    INPUTS[f"triggered_{_lane}"] = (f"io_in_bits_triggered_{_lane}", 4)
INPUTS["walk_vtype_bits_illegal"] = ("io_fromBackend_walkVType_bits_illegal", 1)
INPUTS["walk_vtype_bits_vma"] = ("io_fromBackend_walkVType_bits_vma", 1)
INPUTS["walk_vtype_bits_vta"] = ("io_fromBackend_walkVType_bits_vta", 1)
INPUTS["walk_vtype_bits_vsew"] = ("io_fromBackend_walkVType_bits_vsew", 3)
INPUTS["walk_vtype_bits_vlmul"] = ("io_fromBackend_walkVType_bits_vlmul", 3)
for _lane in range(76):
    INPUTS[f"topdown_reasons_{_lane}"] = (
        f"io_in_bits_topdownInfo_reasons_{_lane}", 1)

OUTPUTS: dict[str, tuple[str, int]] = {
    "in_ready": ("io_in_ready", 1),
    "empty": ("io_empty", 1),
}
for _lane in range(DECODE_WIDTH):
    prefix = f"io_out_{_lane}_bits"
    OUTPUTS[f"out_{_lane}_valid"] = (f"io_out_{_lane}_valid", 1)
    for _name, _width in (("instr", 32), ("foldpc", 10), ("isRvc", 1),
                          ("predTaken", 1), ("trigger", 4),
                          ("crossPageIPFFix", 1), ("backendException", 1),
                          ("satpFlushFirstFetchFault", 1),
                          ("ftqPtr_flag", 1), ("ftqPtr_value", 6),
                          ("ftqOffset", 5)):
        OUTPUTS[f"out_{_lane}_{_name}"] = (f"{prefix}_{_name}", _width)
    for _name, _width in (("exceptionVec_20", 1), ("exceptionVec_19", 1),
                          ("exceptionVec_12", 1), ("exceptionVec_2", 1),
                          ("exceptionVec_1", 1)):
        OUTPUTS[f"out_{_lane}_{_name}"] = (f"{prefix}_{_name}", _width)
    for _field in FIELDS:
        OUTPUTS[f"out_{_lane}_vtype_{_field}"] = (
            f"{prefix}_vtype_{_field}", WIDTHS[_field])
        OUTPUTS[f"out_{_lane}_specvtype_{_field}"] = (
            f"{prefix}_specvtype_{_field}", WIDTHS[_field])
for _lane in range(DECODE_WIDTH):
    OUTPUTS[f"stall_reason_{_lane}"] = (f"io_stallReason_reason_{_lane}", 7)
for _index in range(9):
    OUTPUTS[f"perf_{_index}"] = (f"io_perf_{_index}_value", 6)

INTERFACE = {
    "top": "IBuffer",
    "inputs": {name: (width, port) for name, (port, width) in INPUTS.items()},
    "outputs": {name: (width, port) for name, (port, width) in OUTPUTS.items()},
    "not_compared": {
        "perf_0..8": "performance event counters are bound and exercised but "
                     "their accumulation contract is outside this unit's "
                     "architectural comparison (R-OBS-PERF)",
    },
}


class IBufferPorts:
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
        actual_inputs = {
            name for name, signal in vars(dut).items()
            if name not in {"dut", "clock"} and callable(getattr(signal, "IsInIO", None))
            and signal.IsInIO() and not signal.IsOutIO()
        }
        expected_inputs = {name for name, _ in INPUTS.values()}
        if actual_inputs != expected_inputs:
            raise ValueError(f"IBuffer input ownership mismatch: "
                             f"{actual_inputs ^ expected_inputs}")
        actual_outputs = {
            name for name, signal in vars(dut).items()
            if name not in {"dut", "clock"} and callable(getattr(signal, "IsOutIO", None))
            and signal.IsOutIO()
        }
        expected_outputs = {name for name, _ in OUTPUTS.values()}
        if actual_outputs != expected_outputs:
            raise ValueError(f"IBuffer output ownership mismatch: "
                             f"{actual_outputs ^ expected_outputs}")

    @staticmethod
    def encode(inputs: Inputs) -> dict[str, int]:
        if not isinstance(inputs, Inputs):
            raise TypeError("IBuffer driver requires semantic Inputs")
        values = {
            "reset": inputs.reset,
            "in_valid": inputs.in_valid,
            "valid": inputs.valid,
            "enq_enable": inputs.enq_enable,
            "exception_type": inputs.exception.exc_type,
            "is_backend_exception": inputs.exception.backend_exception,
            "has_satp_flush": inputs.exception.satp_flush,
            "exception_cross_page": inputs.exception.cross_page,
            "exception_mask": inputs.exception_mask,
            "prev_instr_count": inputs.prev_instr_count,
            "flush": inputs.flush,
            "decode_can_accept": inputs.decode_can_accept,
            "resuming_vtype": inputs.resuming_vtype,
            "walk_to_arch_vtype": inputs.walk_to_arch_vtype,
            "walk_vtype_valid": inputs.walk_vtype_valid,
            "vsetvl_vtype_illegal": inputs.vsetvl_vtype.illegal,
            "vsetvl_vtype_vma": inputs.vsetvl_vtype.vma,
            "vsetvl_vtype_vta": inputs.vsetvl_vtype.vta,
            "vsetvl_vtype_vsew": inputs.vsetvl_vtype.vsew,
            "vsetvl_vtype_vlmul": inputs.vsetvl_vtype.vlmul,
            "commit_vtype_valid": inputs.commit_vtype_valid,
            "commit_vtype_illegal": inputs.commit_vtype.illegal,
            "commit_vtype_vma": inputs.commit_vtype.vma,
            "commit_vtype_vta": inputs.commit_vtype.vta,
            "commit_vtype_vsew": inputs.commit_vtype.vsew,
            "commit_vtype_vlmul": inputs.commit_vtype.vlmul,
            "commit_has_vsetvl": inputs.commit_has_vsetvl,
            "backend_redirect": inputs.backend_redirect,
            "control_flow_redirect": inputs.control_flow_redirect,
            "memory_violation_redirect": inputs.memory_violation_redirect,
            "tage_miss_bubble": inputs.tage_miss_bubble,
            "ittage_miss_bubble": inputs.ittage_miss_bubble,
            "ras_miss_bubble": inputs.ras_miss_bubble,
            "walk_vtype_bits_illegal": inputs.walk_vtype.illegal,
            "walk_vtype_bits_vma": inputs.walk_vtype.vma,
            "walk_vtype_bits_vta": inputs.walk_vtype.vta,
            "walk_vtype_bits_vsew": inputs.walk_vtype.vsew,
            "walk_vtype_bits_vlmul": inputs.walk_vtype.vlmul,
        }
        for lane in range(ENQUEUE_WIDTH):
            entry = inputs.entries[lane]
            values[f"instr_{lane}"] = entry.inst
            values[f"is_rvc_{lane}"] = entry.is_rvc
            values[f"foldpc_{lane}"] = entry.foldpc
            if lane < ENQUEUE_WIDTH - 1:
                values[f"pred_taken_{lane}"] = entry.pred_taken
            values[f"offset_{lane}"] = entry.offset
            values[f"ftq_flag_{lane}"] = entry.ftq_flag
            values[f"ftq_value_{lane}"] = entry.ftq_value
            values[f"triggered_{lane}"] = entry.triggered
        for bit in range(76):
            values[f"topdown_reasons_{bit}"] = inputs.topdown_reasons >> bit & 1
        if values.keys() != set(INPUTS):
            raise ValueError("IBuffer encoder must drive every owned input once")
        return values

    def capture(self, event) -> Outputs:
        values = {field: int(value) for field, value in self._outputs.sample().items()}
        lanes = []
        for lane in range(DECODE_WIDTH):
            vtype = VType(**{field: values[f"out_{lane}_vtype_{field}"]
                             for field in FIELDS})
            specvtype = VType(**{field: values[f"out_{lane}_specvtype_{field}"]
                                 for field in FIELDS})
            lanes.append(LaneOutputs(
                valid=values[f"out_{lane}_valid"],
                instr=values[f"out_{lane}_instr"],
                foldpc=values[f"out_{lane}_foldpc"],
                is_rvc=values[f"out_{lane}_isRvc"],
                pred_taken=values[f"out_{lane}_predTaken"],
                ftq_flag=values[f"out_{lane}_ftqPtr_flag"],
                ftq_value=values[f"out_{lane}_ftqPtr_value"],
                ftq_offset=values[f"out_{lane}_ftqOffset"],
                trigger=values[f"out_{lane}_trigger"],
                cross_page_ipf_fix=values[f"out_{lane}_crossPageIPFFix"],
                backend_exception=values[f"out_{lane}_backendException"],
                satp_flush_first_fetch_fault=values[
                    f"out_{lane}_satpFlushFirstFetchFault"],
                exc_page_fault=values[f"out_{lane}_exceptionVec_12"],
                exc_guest_page_fault=values[f"out_{lane}_exceptionVec_20"],
                exc_access_fault=values[f"out_{lane}_exceptionVec_1"],
                exc_illegal=values[f"out_{lane}_exceptionVec_2"],
                exc_hardware_error=values[f"out_{lane}_exceptionVec_19"],
                vtype=vtype,
                specvtype=specvtype,
            ))
        return Outputs(
            in_ready=values["in_ready"],
            full=int(not values["in_ready"]),
            empty=values["empty"],
            lanes=tuple(lanes),
            stall_reason=tuple(values[f"stall_reason_{lane}"]
                               for lane in range(DECODE_WIDTH)),
        )

    def perf(self, event) -> dict[str, int]:
        values = {field: int(value) for field, value in self._outputs.sample().items()}
        return {f"perf_{index}": values[f"perf_{index}"] for index in range(9)}
