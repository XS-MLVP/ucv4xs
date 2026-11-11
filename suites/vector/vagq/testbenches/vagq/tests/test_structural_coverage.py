"""Native structural sweeps for RTL line/branch/toggle coverage.

These are deliberately separate from the semantic protocol tests.  The sweep
drives the generated DUT's public leaves with deterministic values so that
payload bits, mux arms, and state transitions which are not needed by a
particular protocol scenario are still observable.  It does not contribute
functional coverage and it is not an ISA-correctness oracle.
"""

import pytest

from suites.vector.vagq.testbenches.shared.env.structural import randomized_pin_sweep


pytestmark = pytest.mark.toffee_functional_coverage(False)


ROOT = __import__('suites.vector.vagq', fromlist=['ROOT']).ROOT

# The longer runs are intentional: VAGQEntryTable and the control blocks have
# stateful priority networks.  All modules use the same native Verilator DUT
# path as the normal tests; this is not a second simulator.
SWEEPS = (
    pytest.param("VAGQ", True, 20_000, 0x5100, id="VAGQ"),
    pytest.param("VAGQEntryTable", True, 50_000, 0x5101, id="EntryTable"),
    pytest.param("MergeCtrl", True, 50_000, 0x5102, id="MergeCtrl",
                 marks=pytest.mark.selftest),
    pytest.param("SplitCtrl", True, 50_000, 0x5103, id="SplitCtrl",
                 marks=pytest.mark.selftest),
    pytest.param("StoreDataCtrl", True, 50_000, 0x5104, id="StoreDataCtrl",
                 marks=pytest.mark.selftest),
    pytest.param("VAGQArbiter", False, 5_000, 0x5105, id="Arbiter",
                 marks=pytest.mark.selftest),
    pytest.param("OrderedPermitCtrl", True, 5_000, 0x5106, id="Ordered"),
    pytest.param("AddrGen", False, 5_000, 0x5107, id="AddrGen",
                 marks=pytest.mark.selftest),
    pytest.param("MaskGen", False, 5_000, 0x5108, id="MaskGen",
                 marks=pytest.mark.selftest),
    pytest.param("NewPipelineConnectPipe", True, 5_000, 0x5109, id="Pipe",
                 marks=pytest.mark.selftest),
    pytest.param("NewPipelineConnectPipe_3", True, 5_000, 0x510A, id="Pipe3",
                 marks=pytest.mark.selftest),
    pytest.param("VAGQManager", True, 5_000, 0x510B, id="Manager",
                 marks=pytest.mark.selftest),
)


@pytest.mark.parametrize("module,clocked,cycles,seed", SWEEPS)
async def test_native_rtl_structural_sweep(
    module, clocked, cycles, seed, native_registration, tmp_path
):
    if module in {'VAGQ', 'VAGQEntryTable', 'OrderedPermitCtrl'}:
        from suites.vector.vagq.testbenches.vagq.transactions.legal_structural import sweep
        await sweep(module, cycles, seed, tmp_path / module, native_registration)
        return
    randomized_pin_sweep(
        module,
        ROOT / "dut" / module / "signals.json",
        cycles=cycles,
        seed=seed,
        clocked=clocked,
        output=tmp_path / module,
        register=native_registration,
    )
