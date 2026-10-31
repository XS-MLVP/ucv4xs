"""Passive entry requests and SRAM writebacks across all physical banks/ways."""
from suites.frontend.bpu.models.configuration import *
from suites.frontend.bpu.runtime.memory_direct import memory_signal
from suites.frontend.bpu.runtime.memory_direct import memory_signal_names
from dataclasses import dataclass
from dataclasses import field

from toffee import Bundle
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.monitors.cycle import CycleMonitor


ENTRY_FIELDS = (
    ("set_idx", "setIdx"), ("tag", "entry_tag"),
    ("branch_type", "entry_attribute_branchType"),
    ("ras_action", "entry_attribute_rasAction"), ("position", "entry_position"),
    ("carry", "entry_targetCarry_value"), ("lower", "entry_targetLowerBits"),
)


@dataclass
class MbtbEntryActivityTrace:
    feedback: list = field(default_factory=list)
    frames: list = field(default_factory=list)


class MbtbEntryActivityMonitor(CycleMonitor):
    def __init__(self, dut):
        names = tuple(memory_signal_names(dut))

        def signal(align, bank, name):
            suffix = f".MainBtb.alignBanks_{align}.internalBanks_{bank}.entryWriteBuffer.{name}"
            matches = [value for value in names if value.endswith(suffix)]
            if len(matches) != 1:
                raise RuntimeError(f"MainBTB entry signal {suffix} needs one memory-direct binding; found {len(matches)}: {matches}")
            return memory_signal(dut, matches[0].split(".", 1)[1])

        def port(align, bank, way):
            values = {"write_valid": signal(align, bank, f"io_write_{way}_valid"),
                      "read_valid": signal(align, bank, f"io_read_{way}_valid"),
                      "read_ready": signal(align, bank, f"io_read_{way}_ready")}
            for direction in ("write", "read"):
                for key, name in ENTRY_FIELDS:
                    values[f"{direction}_{key}"] = signal(align, bank, f"io_{direction}_{way}_bits_{name}")
            return Bundle(**values)

        banks = tuple(tuple(tuple(port(align, bank, way) for way in range(MAIN_WAYS))
                            for bank in range(MAIN_BANKS)) for align in range(2))
        super().__init__(PortBinding(dut.clock, Bundle(banks=banks), "mbtb.entry_activity"), decoder=self.decode)

    @staticmethod
    def decode(sample):
        def port(value):
            fields = {key: getattr(value, key).as_int() for key in ("write_valid", "read_valid", "read_ready")}
            fields.update({f"{direction}_{key}": getattr(value, f"{direction}_{key}").as_int()
                           for direction in ("write", "read") for key, _ in ENTRY_FIELDS})
            return fields
        return {"banks": tuple(tuple(tuple(port(value) for value in ports) for ports in row)
                               for row in sample.banks)}
