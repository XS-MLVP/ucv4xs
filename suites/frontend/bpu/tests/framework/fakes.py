from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from toffee import Bundle
from toffee import XEvent
from toffee import XEventKind
from toffee import XPhase

from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.bundle.bindings import PulseBinding


def native_name_dut(tmp_path, names=()):
    """A valid native capability with names only; no signal may be dereferenced."""
    layout = tmp_path / 'native-offset.yaml'
    layout.write_text('variables: []\n', encoding='utf-8')
    names = tuple(name.removeprefix('TOP.') for name in names) or ('unrelated.clock',)
    return SimpleNamespace(
        dut=SimpleNamespace(GetXSignalCFGBasePtr=lambda: 1,
                            GetXSignalCFGPath=lambda: str(layout)),
        xcfg=SimpleNamespace(cfg_base_address=1, cfg_data=str(layout),
                             GetSignalNames=lambda: names),
    )


class Signal:
    def __init__(
        self,
        value: int = 0,
        *,
        width: int = 1,
        direction: str = "input",
        name: str = "signal",
    ) -> None:
        self.value = value
        self.width = width
        self.direction = direction
        self.mName = name
        self._rise_write = False

    def Set(self, value: int) -> None:
        self.value = int(value) & ((1 << self.width) - 1)

    def U(self) -> int:
        return self.value

    def W(self) -> int:
        return self.width

    def IsInIO(self) -> bool:
        return self.direction == "input"

    def IsOutIO(self) -> bool:
        return self.direction == "output"

    def IsBiIO(self) -> bool:
        return self.direction == "inout"

    def AsRiseWrite(self) -> None:
        self._rise_write = True

    def IsRiseWrite(self) -> bool:
        return self._rise_write


def bundle_binding(
    *,
    clock: object | None = None,
    direction: str = "input",
    name: str = "request",
) -> tuple[PortBinding, Signal]:
    data = Signal(width=8, direction=direction, name=f"{name}.data")
    interface = PortBinding(
        clock or object(),
        Bundle(data=data),
        name,
    )
    return interface, data


def pulse_binding(
    *,
    clock: object | None = None,
    name: str = "pulse",
) -> tuple[PulseBinding, Signal, Signal]:
    valid = Signal(name=f"{name}.valid")
    data = Signal(width=8, name=f"{name}.data")
    interface = PulseBinding(
        clock or object(),
        valid,
        Bundle(data=data),
        name,
    )
    return interface, valid, data


def event(tick: int) -> XEvent:
    return XEvent(
        event_id=tick,
        tick=tick,
        phase=XPhase.RISING_STABLE,
        kind=XEventKind.CLOCK_RISE,
    )


@dataclass(frozen=True)
class TaggedRequest:
    tag: int


@dataclass(frozen=True)
class TaggedResponse:
    tag: int
