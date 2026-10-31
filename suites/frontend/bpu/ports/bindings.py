"""Bound DUT port groups used by drivers and monitors."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import sys
from typing import Any
from typing import Mapping

from toffee import Bundle
from toffee import as_xdata
from toffee.data import DataNode
from toffee.data import normalize_data
from toffee.data import signal_width


@lru_cache(maxsize=20)
def _port_schema(path: str, identity: tuple[int, ...]):
    return json.loads(Path(path).read_text())


def _tree_node(dut: Any, path: tuple[str, ...], tree=None) -> Mapping[str, Any]:
    # Use standard picker metadata, not injected attributes or patched XPorts.
    if tree is None:
        module = sys.modules[type(dut).__module__]
        schema = Path(module.__file__).with_name('signals.json').resolve()
        stat = schema.stat()
        tree = _port_schema(str(schema), (stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_size))
    node: Any = tree
    for part in path:
        node = node[part]
    if not isinstance(node, Mapping) or "_" in node:
        raise ValueError(f"{'.'.join(path)} is not an aggregate signal-tree node")
    return node


class ConstantLeaf:
    """Read-only constant for a signal the whole-chip build folded away."""

    def __init__(self, value: int, width: int = 1) -> None:
        if width < 1 or type(value) is not int or not 0 <= value < (1 << width):
            raise ValueError("constant value does not fit the declared width")
        self._value = value
        self._width = width

    def U(self) -> int:
        return self._value

    def W(self) -> int:
        return self._width

    def Set(self, value) -> None:
        raise RuntimeError("constant status leaf is read-only")

    def as_int(self) -> int:
        return self._value


def tree_children(dut: Any, path: tuple[str, ...], tree=None) -> tuple[str, ...]:
    """Return the declared child names of one aggregate signal-tree node."""

    node = _tree_node(dut, path, tree)
    return tuple(str(name) for name, value in node.items()
                 if isinstance(value, Mapping))



@dataclass(frozen=True, slots=True)
class PortBinding:
    """Clock and bound data node; no driving or protocol behavior."""

    clock: Any
    bits: DataNode
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("port binding name cannot be empty")
        object.__setattr__(self, "clock", as_xdata(self.clock))
        object.__setattr__(self, "bits", normalize_data(self.bits, self.name))


@dataclass(frozen=True, slots=True)
class PulseBinding:
    """Bound valid and payload signals; PulseDriver owns pulse timing."""

    clock: Any
    valid: Any
    bits: DataNode
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("pulse binding name cannot be empty")
        object.__setattr__(self, "clock", as_xdata(self.clock))
        object.__setattr__(self, "valid", as_xdata(self.valid))
        object.__setattr__(
            self, "bits", normalize_data(self.bits, f"{self.name}.bits")
        )


def _leaf_node(dut: Any, path: tuple[str, ...], tree=None) -> Mapping[str, Any]:
    if tree is None:
        module = sys.modules[type(dut).__module__]
        schema = Path(module.__file__).with_name('signals.json').resolve()
        stat = schema.stat()
        tree = _port_schema(str(schema), (stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_size))
    node: Any = tree
    for part in path:
        node = node[part]
    if not isinstance(node, Mapping) or node.get("_") is not True:
        raise ValueError(f"{'.'.join(path)} is not a leaf signal-tree node")
    return node


def bind_leaf(dut: Any, path: tuple[str, ...], *, name: str | None = None,
              tree: Mapping[str, Any] | None = None) -> Any:
    """Bind one leaf even when its parent sequence has sparse indices.

    Whole-chip DCE can leave only one element of an indexed port (for example
    ABTB's single consumed PHR history). ``Bundle.bind_tree`` rejects such a
    non-contiguous sequence, so callers that need that one leaf resolve it by
    its declared metadata path directly and keep the declared width check.
    """

    node = _leaf_node(dut, path, tree)
    signal = as_xdata(getattr(dut, "_".join(path)))
    if "High" in node:
        high = int(node["High"])
        low = int(node.get("Low", 0))
        expected = 1 if high < 0 else high - low + 1
        if signal_width(signal) != expected:
            raise ValueError(
                f"{name or '.'.join(path)} width mismatch: "
                f"metadata={expected}, actual={signal_width(signal)}"
            )
    return signal


def bind_sequence(dut: Any, path: tuple[str, ...], *, name: str | None = None,
                  tree: Mapping[str, Any] | None = None) -> tuple[Any, ...]:
    """Bind a root-level sequence whose nodes are aggregates.

    ``Bundle.bind_tree`` requires an aggregate root, so a port that is itself
    an array (for example ABTB's four result entries) is bound element by
    element. Sparse element indices are rejected just like bind_bundle.
    """

    label = name or ".".join(path)
    node = _tree_node(dut, path, tree)
    indices = sorted(int(part) for part in node if str(part).isdigit())
    if indices != list(range(len(indices))):
        raise ValueError(f"{label} sequence indices must be contiguous")
    return tuple(
        bind_bundle(dut, path + (str(index),), name=f"{label}[{index}]").bits
        for index in indices
    )


def bind_bundle(dut: Any, path: tuple[str, ...], *, name: str | None = None,
                tree: Mapping[str, Any] | None = None) -> PortBinding:
    label = name or ".".join(path)
    bits = Bundle.bind_tree(
        dut,
        _tree_node(dut, path, tree),
        source_prefix="_".join(path),
        path=label,
    )
    return PortBinding(as_xdata(dut.clock), bits, label)


def bind_pulse(
    dut: Any,
    path: tuple[str, ...],
    *,
    name: str | None = None,
    tree: Mapping[str, Any] | None = None,
) -> PulseBinding:
    label = name or ".".join(path)
    node = _tree_node(dut, path, tree)
    if set(node) != {"valid", "bits"}:
        raise ValueError(f"{label} must contain exactly valid/bits")
    aggregate = Bundle.bind_tree(
        dut,
        node,
        source_prefix="_".join(path),
        path=label,
    )
    return PulseBinding(dut.clock, aggregate.valid, aggregate.bits, label)
