"""Native structural sweeps for RTL line/branch/toggle coverage.

These are deliberately separate from the semantic protocol tests.  The sweep
drives the generated DUT's public leaves with deterministic values so that
payload bits, mux arms, and state transitions which are not needed by a
particular protocol scenario are still observable.  It does not contribute
functional coverage and it is not an ISA-correctness oracle.
"""

import json
from pathlib import Path
import random

import pytest

from vagqverify.native import open_dut


pytestmark = pytest.mark.toffee_functional_coverage(False)


ROOT = Path(__file__).resolve().parents[2]

# The longer runs are intentional: VAGQEntryTable and the control blocks have
# stateful priority networks.  All modules use the same native Verilator DUT
# path as the normal tests; this is not a second simulator.
SWEEPS = (
    pytest.param("VAGQ", True, 20_000, 0x5100, id="VAGQ"),
    pytest.param("VAGQEntryTable", True, 50_000, 0x5101, id="EntryTable"),
    pytest.param("MergeCtrl", True, 50_000, 0x5102, id="MergeCtrl"),
    pytest.param("SplitCtrl", True, 50_000, 0x5103, id="SplitCtrl"),
    pytest.param("StoreDataCtrl", True, 50_000, 0x5104, id="StoreDataCtrl"),
    pytest.param("VAGQArbiter", False, 5_000, 0x5105, id="Arbiter"),
    pytest.param("OrderedPermitCtrl", True, 5_000, 0x5106, id="Ordered"),
    pytest.param("AddrGen", False, 5_000, 0x5107, id="AddrGen"),
    pytest.param("MaskGen", False, 5_000, 0x5108, id="MaskGen"),
    pytest.param("NewPipelineConnectPipe", True, 5_000, 0x5109, id="Pipe"),
    pytest.param("NewPipelineConnectPipe_3", True, 5_000, 0x510A, id="Pipe3"),
    pytest.param("VAGQManager", True, 5_000, 0x510B, id="Manager"),
)


def _input_widths(module):
    schema = json.loads((ROOT / "dut" / module / "signals.json").read_text())

    def leaves(node, prefix=""):
        result = []
        for name, value in node.items():
            path = prefix + name
            if value.get("_") is True:
                high, low = value["High"], value["Low"]
                width = 1 if high < low else high - low + 1
                result.append((path, value["Pin"], width))
            else:
                result.extend(leaves(value, path + "_"))
        return result

    return tuple(
        (name, width)
        for name, pin, width in leaves(schema)
        if pin == "input" and name not in {"clock", "reset"}
    )


@pytest.mark.parametrize("module,clocked,cycles,seed", SWEEPS)
def test_native_rtl_structural_sweep(
    module, clocked, cycles, seed, native_registration, tmp_path
):
    inputs = _input_widths(module)
    rng = random.Random(seed)
    values = {name: 0 for name, _width in inputs}

    with open_dut(
        module,
        tmp_path / module,
        clocked=clocked,
        register=native_registration,
    ) as dut:
        for name, _width in inputs:
            getattr(dut, name).AsImmWrite()

        if clocked:
            dut.reset.AsImmWrite()
            dut.reset.Set(1)
            dut.Step(2)
            dut.reset.Set(0)
            dut.Step(1)

        for _cycle in range(cycles):
            for name, width in inputs:
                values[name] = rng.getrandbits(width)
            for name, value in values.items():
                getattr(dut, name).Set(value)
            if clocked:
                dut.Step(1)
            else:
                dut.RefreshComb()
