"""Semantic StoreDataCtrl inputs and public observations."""
from dataclasses import dataclass


NUM_ENTRIES = 8
SPLIT = 3
ALL_BYTES = 0xffff


@dataclass(frozen=True, slots=True)
class Entry:
    valid: bool = False
    uop_type: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    psrc2: int = 0
    deew: int = 0
    start_byte: int = 0
    elem_active: int = 0
    req_ack: int = 0
    data_sent: int = 0
    state: int = 0
    sq_first_flag: int = 0
    sq_second_flag: int = 0
    sq_value: int = 0
    ordered_can_proceed: bool = True

    @property
    def is_store(self):
        return bool(self.uop_type & 1)


@dataclass(frozen=True, slots=True)
class Redirect:
    valid: bool = False
    level: int = 0
    rob_flag: int = 0
    rob_value: int = 0


@dataclass(frozen=True, slots=True)
class VrfReadResponse:
    valid: bool = False
    entry_idx: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    data: int = 0


@dataclass(frozen=True, slots=True)
class VrfReadRequest:
    valid: bool = False
    entry_idx: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    psrc2: int = 0


@dataclass(frozen=True, slots=True)
class StoreDataRequest:
    sq_first_flag: int
    sq_second_flag: int
    sq_value: int
    data: int


@dataclass(frozen=True, slots=True)
class Update:
    valid: bool = False
    entry_idx: int = 0
    set_data_sent: int = 0


@dataclass(frozen=True, slots=True)
class Beat:
    entries: tuple[Entry, ...] = (Entry(),) * NUM_ENTRIES
    psrc2_ready: tuple[bool, ...] = (False,) * NUM_ENTRIES
    redirect: Redirect = Redirect()
    older_matrix: tuple[tuple[bool, ...], ...] = tuple(
        tuple(False for _ in range(NUM_ENTRIES)) for _ in range(NUM_ENTRIES)
    )
    vrf_read_req_ready: bool = False
    vrf_read_resp: VrfReadResponse = VrfReadResponse()
    store_data_ready: tuple[bool, bool] = (False, False)


@dataclass(frozen=True, slots=True)
class Observation:
    vrf_read_req: VrfReadRequest
    store_data: tuple[StoreDataRequest | None, StoreDataRequest | None]
    update: tuple[Update, Update]
