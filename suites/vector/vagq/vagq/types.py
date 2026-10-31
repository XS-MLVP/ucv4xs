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
class Observation:
    outputs: dict[str, int]
    active: tuple[RequestEvent, ...] = field(default_factory=tuple)
    empty: tuple[RequestEvent, ...] = field(default_factory=tuple)
