"""Native binding, encoding and capture for the VTypeGen leaf DUT.

Every generated input and output is bound with an exact width and direction.
The 80 vtype outputs are grouped into the two eight-lane windows the interface
defines; no port is silently ignored.
"""

from __future__ import annotations

from toffee import Bundle

from suites.frontend.ibuffer.testbenches.vtype_gen.model import DECODE_WIDTH
from suites.frontend.ibuffer.testbenches.vtype_gen.model import Inputs
from suites.frontend.ibuffer.testbenches.vtype_gen.model import Outputs
from suites.frontend.ibuffer.testbenches.vtype_gen.model import VType

FIELDS = ("illegal", "vma", "vta", "vsew", "vlmul")
WIDTHS = {"illegal": 1, "vma": 1, "vta": 1, "vsew": 3, "vlmul": 3}

INPUTS: dict[str, tuple[str, int]] = {"reset": ("reset", 1)}
for _lane in range(DECODE_WIDTH):
    INPUTS[f"insts_{_lane}_valid"] = (f"in_insts_{_lane}_valid", 1)
    INPUTS[f"insts_{_lane}_bits"] = (f"in_insts_{_lane}_bits", 32)
INPUTS["walk_to_arch_vtype"] = ("in_walkToArchVType", 1)
INPUTS["walk_vtype_valid"] = ("in_walkVType_valid", 1)
for _field in FIELDS:
    INPUTS[f"walk_vtype_{_field}"] = (f"in_walkVType_bits_{_field}", WIDTHS[_field])
INPUTS["can_update_vtype"] = ("in_canUpdateVType", 1)
for _field in FIELDS:
    INPUTS[f"vsetvl_vtype_{_field}"] = (f"in_vsetvlVType_{_field}", WIDTHS[_field])
INPUTS["commit_vtype_valid"] = ("in_commitVType_vtype_valid", 1)
for _field in FIELDS:
    INPUTS[f"commit_vtype_{_field}"] = (f"in_commitVType_vtype_bits_{_field}",
                                       WIDTHS[_field])
INPUTS["commit_has_vsetvl"] = ("in_commitVType_hasVsetvl", 1)

OUTPUTS: dict[str, tuple[str, int]] = {}
for _lane in range(DECODE_WIDTH):
    for _field in FIELDS:
        OUTPUTS[f"vtype_{_lane}_{_field}"] = (
            f"out_vtype_{_lane}_{_field}", WIDTHS[_field])
for _lane in range(DECODE_WIDTH):
    for _field in FIELDS:
        OUTPUTS[f"specvtype_{_lane}_{_field}"] = (
            f"out_specvtype_{_lane}_{_field}", WIDTHS[_field])

INTERFACE = {
    "top": "VTypeGen",
    "inputs": {name: (width, port) for name, (port, width) in INPUTS.items()},
    "outputs": {name: (width, port) for name, (port, width) in OUTPUTS.items()},
}


class VTypeGenPorts:
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
            raise ValueError(f"VTypeGen input ownership mismatch: "
                             f"{actual_inputs ^ expected_inputs}")
        actual_outputs = {
            name for name, signal in vars(dut).items()
            if name not in {"dut", "clock"} and callable(getattr(signal, "IsOutIO", None))
            and signal.IsOutIO()
        }
        expected_outputs = {name for name, _ in OUTPUTS.values()}
        if actual_outputs != expected_outputs:
            raise ValueError(f"VTypeGen output ownership mismatch: "
                             f"{actual_outputs ^ expected_outputs}")

    @staticmethod
    def encode(inputs: Inputs) -> dict[str, int]:
        if not isinstance(inputs, Inputs):
            raise TypeError("VTypeGen driver requires semantic Inputs")
        values = {"reset": inputs.reset}
        for lane, (valid, bits) in enumerate(inputs.insts):
            values[f"insts_{lane}_valid"] = valid
            values[f"insts_{lane}_bits"] = bits
        values["walk_to_arch_vtype"] = inputs.walk_to_arch_vtype
        values["walk_vtype_valid"] = inputs.walk_vtype_valid
        for field in FIELDS:
            values[f"walk_vtype_{field}"] = getattr(inputs.walk_vtype, field)
        values["can_update_vtype"] = inputs.can_update_vtype
        for field in FIELDS:
            values[f"vsetvl_vtype_{field}"] = getattr(inputs.vsetvl_vtype, field)
        values["commit_vtype_valid"] = inputs.commit_vtype_valid
        for field in FIELDS:
            values[f"commit_vtype_{field}"] = getattr(inputs.commit_vtype, field)
        values["commit_has_vsetvl"] = inputs.commit_has_vsetvl
        if values.keys() != set(INPUTS):
            raise ValueError("VTypeGen encoder must drive every owned input once")
        return values

    def capture(self, event) -> Outputs:
        values = {field: int(value) for field, value in self._outputs.sample().items()}
        vtype = tuple(VType(**{field: values[f"vtype_{lane}_{field}"]
                               for field in FIELDS})
                      for lane in range(DECODE_WIDTH))
        specvtype = tuple(VType(**{field: values[f"specvtype_{lane}_{field}"]
                                   for field in FIELDS})
                          for lane in range(DECODE_WIDTH))
        return Outputs(vtype=vtype, specvtype=specvtype)
