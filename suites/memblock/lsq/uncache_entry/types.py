from dataclasses import dataclass

from suites.memblock.lsq.vlq.types import QueuePtr, Redirect, RobPtr

SOURCE_EXCEPTION_BITS = (23, 21, 15, 13, 7, 6, 4, 3)
SOURCE_EXCEPTION_MASK = sum(1 << bit for bit in SOURCE_EXCEPTION_BITS)


@dataclass(frozen=True)
class Request:
    valid: bool = False
    rob: RobPtr = RobPtr()
    lq: QueuePtr = QueuePtr()
    vaddr: int = 0
    fullva: int = 0
    paddr: int = 0
    gpaddr: int = 0
    mask: int = 0
    nc: bool = False
    mmio: bool = False
    memory_backed: bool = False
    hyper: bool = False
    nonleaf: bool = False
    exceptions: int = 0


@dataclass(frozen=True)
class IdResponse:
    valid: bool = False
    mid: int = 0
    sid: int = 0


@dataclass(frozen=True)
class Response:
    valid: bool = False
    data: int = 0
    error: bool = False
    nderr: bool = False


@dataclass(frozen=True)
class Inputs:
    request: Request = Request()
    pending: RobPtr = RobPtr()
    redirect: Redirect = Redirect()
    bus_ready: bool = False
    id_response: IdResponse = IdResponse()
    response: Response = Response()
    mmio_wake_ready: bool = True
    nc_wake_ready: bool = True
    mmio_ready: bool = False
    nc_ready: bool = False
    reset: bool = False


@dataclass(frozen=True)
class Wakeup:
    valid: bool = False
    lq: QueuePtr = QueuePtr()


@dataclass(frozen=True)
class DataOutput:
    valid: bool = False
    lq: QueuePtr = QueuePtr()
    paddr: int = 0
    data: int = 0
    error: bool = False
    nderr: bool = False


@dataclass(frozen=True)
class BusRequest:
    valid: bool = False
    rob: RobPtr = RobPtr()
    paddr: int = 0
    vaddr: int = 0
    mask: int = 0
    nc: bool = False
    memory_backed: bool = False


@dataclass(frozen=True)
class FaultReport:
    valid: bool = False
    rob: RobPtr = RobPtr()
    fullva: int = 0
    gpaddr: int = 0
    hyper: bool = False
    nonleaf: bool = False
    exceptions: int = 0


@dataclass(frozen=True)
class Outputs:
    flush: bool
    mmio_select: bool
    slave_valid: bool
    slave_id: int
    bus: BusRequest
    mmio_wakeup: Wakeup
    nc_wakeup: Wakeup
    mmio: DataOutput
    nc: DataOutput
    exception: FaultReport


@dataclass(frozen=True)
class Owner:
    uid: int
    request: Request


@dataclass(frozen=True)
class Change:
    before: Owner | None = None
    allocated: Owner | None = None
    phase_before: str = "empty"
    phase_after: str = "empty"
    issued: bool = False
    bound: bool = False
    responded: bool = False
    woke: bool = False
    consumed: bool = False
    retired: bool = False
    canceled: bool = False
    deferred_before: bool = False
    deferred_after: bool = False
    reset_kind: str | None = None
