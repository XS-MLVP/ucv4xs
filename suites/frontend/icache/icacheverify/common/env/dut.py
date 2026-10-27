from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from toffee import as_xdata
from toffee.signals import signal_identity

from icacheverify.common.env.memory_direct import require_memory_direct
from icacheverify.common.env.runtime import validate_dut_runtime
from icacheverify.common.env.artifacts import isolated_outputs
from icacheverify.common.env.artifacts import output_directory
from icacheverify.common.coverage.native import collect_native_coverage
from icacheverify.common.coverage.native import native_coverage_path


ROOT = Path(__file__).resolve().parents[3]
RTL_COVERAGE_FILES: set[Path] = set()
VERILATOR_SEED = 1


def initialize_dut_inputs(dut: Any) -> None:
    """Start in reset, zero other inputs, then enable rising-phase writes."""

    clock_identity = signal_identity(as_xdata(dut.clock))
    reset_identity = signal_identity(as_xdata(dut.reset))
    for signal in vars(dut).values():
        data = as_xdata(signal)
        if callable(getattr(data, "IsInIO", None)) and data.IsInIO():
            data.AsImmWrite()
            data.Set(1 if signal_identity(data) == reset_identity else 0)
            if signal_identity(data) != clock_identity:
                data.AsRiseWrite()


class DutFactory:
    """Function-scoped pytest resource owner for generated native DUTs."""

    def __init__(self, *, managed_coverage: bool = False, coverage_register=None) -> None:
        self.managed_coverage = managed_coverage
        self.coverage_register = coverage_register
        self._instances: list[tuple[Any, Path | None, str]] = []

    def create(self, name: str, *, coverage_name: str = "verilator-coverage.dat") -> Any:
        directory = ROOT / "dut" / name
        module_name = f"kunminghu_v3_pytest_{name}_{len(self._instances)}"
        spec = importlib.util.spec_from_file_location(
            module_name,
            directory / "__init__.py",
            submodule_search_locations=[str(directory)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load generated DUT {name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        validate_dut_runtime(module.xsp)
        cls = next(value for key, value in vars(module).items() if key.startswith("DUT"))
        result_dir = output_directory(ROOT, name)
        if not self.managed_coverage:
            result_dir.mkdir(parents=True, exist_ok=True)
        if isolated_outputs():
            coverage_name = f'{len(self._instances)}-{Path(coverage_name).name}'
        coverage_path = None if self.managed_coverage else native_coverage_path(name, result_dir / coverage_name)
        # picker enables random initialization of Verilator registers. A
        # nonzero plusarg fixes that randomness per DUT instance, so testcase
        # order cannot silently change uncovered RTL counter-clone results.
        args = module.xsp.StringVector([name, f"+verilator+seed+{VERILATOR_SEED}"])
        dut = cls(args, coverage_filename=str(coverage_path) if coverage_path is not None else '')
        try:
            view = require_memory_direct(dut)
            if not view._metadata:
                raise RuntimeError('DUT requires trace-derived signal mappings; rebuild with --rw mem_direct -w memory-direct.fst')
            # Compile trace for YAML reconstruction, but do not dump waveforms
            # during ordinary pytest runs. This does not disable native reads.
            dut.dut.WaveformEnable(False)
        except BaseException:
            dut.Finish()
            raise
        dut.InitClock("clock")
        # Assert reset before the first clock tick, so random Verilator
        # register initialization cannot become part of a functional epoch.
        # xcomm commits subsequent transaction writes on the rising phase.
        initialize_dut_inputs(dut)
        self._instances.append((dut, coverage_path, name))
        if self.coverage_register is not None:
            self.coverage_register(dut)
        return dut

    def close(self) -> None:
        while self._instances:
            dut, coverage_path, name = self._instances.pop()
            require_memory_direct(dut).close()
            dut.Finish()
            if coverage_path is not None and coverage_path.is_file():
                RTL_COVERAGE_FILES.add(collect_native_coverage(name, coverage_path))
