"""Native-memory access and trace-derived read views, without VPI/DPI fallback."""
from __future__ import annotations

from operator import index
from pathlib import Path
from typing import Any
from functools import lru_cache

import yaml


@lru_cache(maxsize=20)
def _trace_metadata(path: str, identity: tuple[int, ...]):
    """Cache model-independent metadata, never native addresses or XData handles."""
    data = yaml.load(Path(path).read_bytes(), Loader=yaml.CSafeLoader)
    return {entry['name']: entry for entry in data.get('signals', ())}


class MemoryDirectSignals:
    """Own native XData handles for one live picker model and its exact layout."""

    def __init__(self, dut: Any):
        native = getattr(dut, 'dut', None)
        get_base = getattr(native, 'GetXSignalCFGBasePtr', None)
        get_path = getattr(native, 'GetXSignalCFGPath', None)
        if not callable(get_base) or not callable(get_path):
            raise RuntimeError('DUT requires picker --rw mem_direct; no native-memory interface')
        self.base = int(get_base())
        if self.base <= 0:
            raise RuntimeError('DUT requires picker --rw mem_direct; native model base is zero (VPI fallback forbidden)')
        self.layout = Path(get_path())
        if not self.layout.is_file() or self.layout.stat().st_size == 0:
            raise RuntimeError(f'memory-direct offset layout missing or empty: {self.layout}')
        self.cfg = getattr(dut, 'xcfg', None)
        if self.cfg is None or int(self.cfg.cfg_base_address) != self.base:
            raise RuntimeError('memory-direct CFG is missing or belongs to another model base')
        if Path(self.cfg.cfg_data).resolve() != self.layout.resolve():
            raise RuntimeError('memory-direct CFG does not match the model offset layout')
        self.owner, self.closed = dut, False
        self._names = frozenset(self.cfg.GetSignalNames())
        if not self._names:
            raise RuntimeError('memory-direct layout contains no signals')
        stat = self.layout.stat()
        self._metadata = _trace_metadata(str(self.layout.resolve()),
            (stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_size))
        # Discovery uses logical RTL trace declarations. Raw native storage
        # also includes compiler temporaries such as __Vdly__<hierarchy>, which
        # must not appear as a second RTL port with the same suffix.
        self._discovery_names = frozenset(self._metadata) if self._metadata else self._names
        self._signals: dict[tuple[str, int | None], Any] = {}

    def _require_live(self):
        if self.closed:
            raise RuntimeError('memory-direct signal view belongs to a closed DUT')

    def names(self) -> tuple[str, ...]:
        self._require_live()
        # Existing observation schemas use a synthetic TOP root. It is only
        # naming normalization; all lookups below go directly through XSignalCFG.
        return tuple('TOP.' + name for name in sorted(self._discovery_names))

    def signal(self, name: str, array_index: int | None = None):
        self._require_live()
        name = name.removeprefix('TOP.')
        if name not in self._names:
            raise RuntimeError(f'memory-direct signal unavailable: {name}')
        metadata = self._metadata.get(name, {})
        derived = metadata.get('kind') in ('projection', 'expr', 'const')
        # At() describes storage only. Installed versions return None and log
        # an error for valid derived views; do not mistake that for no signal.
        cfg = None if derived else self.cfg.At(name)
        direct = cfg is not None and not cfg.is_empty
        if direct:
            width, stride = int(cfg.rtl_width), int(cfg.mem_bytes)
            required = 1 if width <= 8 else 2 if width <= 16 else 4 if width <= 32 else 8 if width <= 64 else 4 * ((width + 31) // 32)
            if width <= 0 or stride != required:
                raise RuntimeError(f'unsafe native-memory layout for {name}: width={width}, stride={stride}, required={required}')
        # XSignalCFG owns trace-derived projection/expr/const read views. These
        # are valid memory-direct observations, not missing physical fields.
        size = int(cfg.array_size) if direct else 0
        if array_index is None:
            if size:
                raise ValueError(f'native array requires an explicit element index: {name}')
        else:
            array_index = index(array_index)
            if not 0 <= array_index < size:
                raise IndexError(f'native array index out of bounds: {name}[{array_index}], size={size}')
        key = (name, array_index)
        if key not in self._signals:
            label = 'MEM_DIRECT:' + name
            signal = self.cfg.NewXData(name, label) if array_index is None else self.cfg.NewXData(name, array_index, label)
            if signal is None or signal.IsVPIBinded():
                raise RuntimeError(f'native-memory binding failed (VPI fallback forbidden): {name}')
            if direct and signal.W() != (0 if width == 1 else width):
                raise RuntimeError(f'native-memory XData width does not match layout: {name}')
            if not direct and not signal.IsOutIO():
                raise RuntimeError(f'trace-derived signal must be read-only: {name}')
            if derived and signal.W() != (0 if metadata['rtl_width'] == 1 else metadata['rtl_width']):
                raise RuntimeError(f'trace-derived XData width does not match layout: {name}')
            self._signals[key] = signal
        return self._signals[key]

    def close(self):
        self.closed = True


def require_memory_direct(dut: Any) -> MemoryDirectSignals:
    view = getattr(dut, '_memory_direct_view', None)
    if view is None:
        view = MemoryDirectSignals(dut)
        dut._memory_direct_view = view
    view._require_live()
    return view


def memory_signal_names(dut: Any) -> tuple[str, ...]:
    return require_memory_direct(dut).names()


def memory_signal(dut: Any, name: str, array_index: int | None = None):
    return require_memory_direct(dut).signal(name, array_index)
