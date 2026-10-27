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


def flat_leaf_names(dut: Any, root: str) -> list[str]:
    """Flatten one ``signals.json`` subtree into the generator's leaf names.

    Large SRAM wrappers expose Vec-indexed BIST ports whose field names are not
    valid Python identifiers, so they cannot be expressed as a ``Bundle``. They
    are always held low and are therefore collected as flat leaves.
    """
    import json
    import sys
    from pathlib import Path

    module = sys.modules[type(dut).__module__]
    schema = json.loads(Path(module.__file__).with_name("signals.json").read_text())
    names: list[str] = []

    def walk(node: dict, prefix: str) -> None:
        for key, value in node.items():
            flat = f"{prefix}_{key}"
            if isinstance(value, dict) and value.get("_"):
                names.append(flat)
            elif isinstance(value, dict):
                walk(value, flat)

    walk(schema[root], root)
    return names
