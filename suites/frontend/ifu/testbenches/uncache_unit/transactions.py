"""Byte-address transactions and immutable observations; UIDs are environment-only."""
from dataclasses import dataclass

from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import Inputs
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import NC
from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import Outputs


@dataclass(frozen=True)
class ReadRequest:
    paddr: int
    is_mmio: int = 0
    pbmt: int = NC

    def __post_init__(self):
        Inputs(req_paddr=self.paddr, req_is_mmio=self.is_mmio, req_pbmt=self.pbmt)


@dataclass(frozen=True)
class BusReply:
    data: int
    corrupt: int = 0
    denied: int = 0
    need_resend: int = 0

    def __post_init__(self):
        Inputs(from_valid=1, from_data=self.data, from_corrupt=self.corrupt,
               from_denied=self.denied, from_need_resend=self.need_resend)


@dataclass(frozen=True)
class Frame:
    inputs: Inputs = Inputs()
    reset: int = 0

    def __post_init__(self):
        if not isinstance(self.inputs, Inputs):
            raise TypeError('Uncache frame requires semantic Inputs')
        if not isinstance(self.reset, int) or self.reset not in (0, 1):
            raise ValueError('reset must be a boolean encoding')


@dataclass(frozen=True)
class RequestRecord:
    uid: int
    epoch: int
    request: ReadRequest
    scope: str
    state: str = 'offered'
    fire_tick: int | None = None
    issued_tick: int | None = None
    terminal_tick: int | None = None
    reason: str | None = None


@dataclass(frozen=True)
class Events:
    offered_uid: int | None = None
    req_fire_uid: int | None = None
    accepted_uid: int | None = None
    bus_fire_uid: int | None = None
    completed_uid: int | None = None
    cancelled_uids: tuple[int, ...] = ()
    previous_completion_uid: int | None = None
    response_uid: int | None = None


@dataclass(frozen=True)
class Status:
    phase: str  # Independent protocol progress, not a peek at an RTL state register.
    epoch: int
    offered_cycles: int
    req_fires: int
    accepted: int
    flushed_on_accept: int
    issued: int
    completed: int
    cancelled: int
    response_fires: int
    ignored_responses: int
    active_uid: int | None


@dataclass(frozen=True)
class CheckedCycle:
    sequence: int
    before_tick: int
    after_tick: int
    before: Outputs
    after: Outputs
    events: Events
    status: Status


@dataclass(frozen=True)
class CompletedRead:
    uid: int
    response: BusReply
    cycle: CheckedCycle
