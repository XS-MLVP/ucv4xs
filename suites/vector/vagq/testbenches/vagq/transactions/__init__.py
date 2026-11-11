"""Human-readable external packets for the VAGQ integration boundary."""
from dataclasses import dataclass, field


FLOW_BYTES = 16
VAGQ_SIZE = 8


@dataclass(frozen=True, slots=True)
class AddrPacket:
    entry_idx: int = 0
    uop_type: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    pdest: int = 0
    psrc2: int = 0
    base_addr: int = 0
    v0_byte_mask: int = 1
    deew: int = 0
    ieew: int = 0
    emul: int = 0
    vl: int = 1
    vstart: int = 0
    vma: int = 0
    vta: int = 0
    uop_idx: int = 0
    last_uop: int = 1
    nf: int = 0
    ftq_flag: int = 0
    ftq_value: int = 0
    ftq_offset: int = 0
    lq_flag: int = 0
    lq_value: int = 0
    sq_first_flag: int = 0
    sq_second_flag: int = 0
    sq_value: int = 0
    vsew: int = 0
    vlmul: int = 0


@dataclass(frozen=True, slots=True)
class DataPacket:
    entry_idx: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    op2_data: int = 0


@dataclass(frozen=True, slots=True)
class NativePacket:
    """Opaque native issue payload; only public leaves are accepted."""

    valid: bool = False
    fields: tuple[tuple[str, int], ...] = ()

    @classmethod
    def from_dict(cls, valid=False, **fields):
        return cls(bool(valid), tuple(sorted((key, int(value)) for key, value in fields.items())))

    def values(self):
        return dict(self.fields)


@dataclass(frozen=True, slots=True)
class Response:
    valid: bool = False
    entry_idx: int = 0
    issue_mask: int = 0
    is_nack: int = 0
    exception: int = 0
    exception_number: int = 0
    fault_elem_idx: int = 0


@dataclass(frozen=True, slots=True)
class EmptyResponse:
    valid: bool = False
    entry_idx: int = 0
    issue_mask: int = 0
    is_nack: int = 0


@dataclass(frozen=True, slots=True)
class VrfResponse:
    valid: bool = False
    entry_idx: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    data: int = 0


@dataclass(frozen=True, slots=True)
class Redirect:
    valid: bool = False
    level: int = 0
    rob_flag: int = 0
    rob_value: int = 0


def _empty_tuple(value, count):
    return tuple(value for _ in range(count))


@dataclass(frozen=True, slots=True)
class Beat:
    addr: tuple[AddrPacket | None, AddrPacket | None] = (None, None)
    addr_valid: tuple[bool, bool] = (False, False)
    stride: tuple[DataPacket | None, DataPacket | None] = (None, None)
    stride_valid: tuple[bool, bool] = (False, False)
    index: tuple[DataPacket | None, DataPacket | None] = (None, None)
    index_valid: tuple[bool, bool] = (False, False)
    issue_lda: tuple[NativePacket, NativePacket, NativePacket] = (
        NativePacket(), NativePacket(), NativePacket())
    issue_sta: tuple[NativePacket, NativePacket] = (NativePacket(), NativePacket())
    ldu_ready: tuple[bool, bool, bool] = (True, True, True)
    sta_ready: tuple[bool, bool] = (True, True)
    empty_ready: tuple[bool, bool] = (True, True)
    std_busy: tuple[bool, bool] = (False, False)
    ldu_resp: tuple[Response, Response, Response] = (
        Response(), Response(), Response())
    sta_resp: tuple[Response, Response] = (Response(), Response())
    empty_resp: tuple[EmptyResponse, EmptyResponse] = (
        EmptyResponse(), EmptyResponse())
    vrf_resp: VrfResponse = VrfResponse()
    psrc2_ready_mask: int = (1 << 128) - 1
    redirect: Redirect = Redirect()


@dataclass(frozen=True, slots=True)
class RequestEvent:
    kind: str
    lane: int
    entry_idx: int
    byte_offset: int
    elem_idx: int
    issue_mask: int
    data_mask: int
    vaddr: int
    is_load: bool
    fired: bool


@dataclass(frozen=True, slots=True)
class ActiveRequest:
    """Immutable snapshot of one valid public LSU/STA request lane."""

    group: str
    lane: int
    valid: bool = False
    meta_valid: bool = False
    entry_idx: int = 0
    byte_offset: int = 0
    elem_idx: int = 0
    data_mask: int = 0
    data_size: int = 0
    vaddr: int = 0
    pc: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    lq_flag: int = 0
    lq_value: int = 0
    sq_first_flag: int = 0
    sq_second_flag: int = 0
    sq_value: int = 0
    ftq_flag: int = 0
    ftq_value: int = 0
    ftq_offset: int = 0
    pdest: int = 0
    ctrl_fu_type: int = 0
    ctrl_vec_wen: int = 0


@dataclass(frozen=True, slots=True)
class EmptyRequest:
    lane: int
    valid: bool = False
    entry_idx: int = 0
    issue_mask: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    is_load: int = 0
    lq_value: int = 0
    sq_value: int = 0


@dataclass(frozen=True, slots=True)
class VrfRead:
    valid: bool = False
    entry_idx: int = 0
    rob_flag: int = 0
    rob_value: int = 0


@dataclass(frozen=True, slots=True)
class VrfWrite:
    valid: bool = False
    entry_idx: int = 0
    pdest: int = 0
    mask: int = 0
    data: int = 0


@dataclass(frozen=True, slots=True)
class StoreData:
    lane: int
    valid: bool = False
    sq_first_flag: int = 0
    sq_second_flag: int = 0
    sq_value: int = 0
    data: int = 0


@dataclass(frozen=True, slots=True)
class Writeback:
    valid: bool = False
    entry_idx: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    exception: int = 0
    exception_number: int = 0
    fault_vstart: int = 0
    uop_idx: int = 0
    uop_type: int = 0
    nf: int = 0
    deew: int = 0


@dataclass(frozen=True, slots=True)
class Wakeup:
    valid: bool = False
    pdest: int = 0


@dataclass(frozen=True, slots=True)
class AdmissionStatus:
    """Immutable view of the admitted-entry accounting."""

    entry_idx: int
    complete: bool
    writeback_seen: bool
    flushed: bool
    emitted_active: frozenset[int]
    emitted_empty: frozenset[int]

    def __post_init__(self):
        object.__setattr__(self, 'emitted_active', frozenset(self.emitted_active))
        object.__setattr__(self, 'emitted_empty', frozenset(self.emitted_empty))


def _lane_snapshot(values, item_type, count, *, group=None):
    """Copy a lane sequence and prove its fixed shape and identity."""
    copied = tuple(values)
    if len(copied) != count:
        raise ValueError(
            f'{item_type.__name__} snapshot must have exactly {count} lanes, '
            f'got {len(copied)}'
        )
    for lane, item in enumerate(copied):
        if not isinstance(item, item_type):
            raise TypeError(
                f'{item_type.__name__}[{lane}] must be {item_type.__name__}, '
                f'got {type(item).__name__}'
            )
        if item.lane != lane:
            raise ValueError(
                f'{item_type.__name__}[{lane}] identifies lane {item.lane}'
            )
        if group is not None and getattr(item, 'group', group) != group:
            raise ValueError(
                f'{item_type.__name__}[{lane}] identifies group '
                f'{getattr(item, "group", None)!r}, expected {group!r}'
            )
    return copied


@dataclass(frozen=True, slots=True)
class Observation:
    """Immutable one-cycle snapshot decoded at the ticket-entry boundary.

    Sequences are copied into tuples and fixed per-lane identity is checked in
    ``__post_init__``; callers never retain a live list reference through the
    snapshot.
    """

    cycle: int = 0
    addr_ready: tuple[bool, bool] = (False, False)
    # Same-cycle target ready evidence captured with the sample.  ``None``
    # means "no evidence captured"; a tuple (including all-False) is positive
    # evidence of that exact handshake.  Response construction must not
    # collapse these two states into one.
    ldu_ready: tuple[bool, bool, bool] | None = None
    sta_ready: tuple[bool, bool] | None = None
    empty_ready: tuple[bool, bool] | None = None
    loads: tuple[ActiveRequest, ...] = field(default_factory=lambda: tuple(
        ActiveRequest('load', lane) for lane in range(3)))
    stores: tuple[ActiveRequest, ...] = field(default_factory=lambda: tuple(
        ActiveRequest('store', lane) for lane in range(2)))
    empty_requests: tuple[EmptyRequest, ...] = field(default_factory=lambda: tuple(
        EmptyRequest(lane) for lane in range(2)))
    vrf_read: VrfRead = VrfRead()
    vrf_write: VrfWrite = VrfWrite()
    store_data: tuple[StoreData, ...] = field(default_factory=lambda: tuple(
        StoreData(lane) for lane in range(2)))
    writeback: Writeback = Writeback()
    wakeup: Wakeup = Wakeup()

    def __post_init__(self):
        if not isinstance(self.cycle, int) or self.cycle < 0:
            raise ValueError(f'observation cycle must be a non-negative int: {self.cycle!r}')
        for name, value, count in (
            ('addr_ready', self.addr_ready, 2),
            ('ldu_ready', self.ldu_ready, 3),
            ('sta_ready', self.sta_ready, 2),
            ('empty_ready', self.empty_ready, 2),
        ):
            if value is None and name != 'addr_ready':
                continue
            ready = tuple(value)
            if len(ready) != count or not all(isinstance(v, bool) for v in ready):
                raise ValueError(f'{name} must be {count} booleans')
            object.__setattr__(self, name, ready)
        object.__setattr__(
            self, 'loads',
            _lane_snapshot(self.loads, ActiveRequest, 3, group='load'))
        object.__setattr__(
            self, 'stores',
            _lane_snapshot(self.stores, ActiveRequest, 2, group='store'))
        object.__setattr__(
            self, 'empty_requests',
            _lane_snapshot(self.empty_requests, EmptyRequest, 2))
        object.__setattr__(
            self, 'store_data',
            _lane_snapshot(self.store_data, StoreData, 2))
        for name, value, expected in (
            ('vrf_read', self.vrf_read, VrfRead),
            ('vrf_write', self.vrf_write, VrfWrite),
            ('writeback', self.writeback, Writeback),
            ('wakeup', self.wakeup, Wakeup),
        ):
            if not isinstance(value, expected):
                raise TypeError(f'{name} must be {expected.__name__}')

    @property
    def has_ready_evidence(self):
        """True when every target-ready group was sampled this cycle."""
        return (
            self.ldu_ready is not None
            and self.sta_ready is not None
            and self.empty_ready is not None
        )

    @property
    def active_requests(self):
        return tuple(
            request for request in self.loads + self.stores
            if request.valid and request.meta_valid
        )

    @property
    def empty_valid(self):
        return tuple(request for request in self.empty_requests if request.valid)
