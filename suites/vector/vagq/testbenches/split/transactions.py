"""Semantic SplitCtrl input beats and observable requests."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Entry:
    valid: bool = False
    uop_type: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    pdest: int = 0
    base_addr: int = 0
    op2_data: int = 0
    ieew: int = 0
    deew: int = 0
    elem_base: int = 0
    start_field: int = 0
    start_byte: int = 0
    elem_valid: int = 0
    elem_active: int = 0
    nf: int = 0
    req_sent: int = 0
    req_ack: int = 0
    exception: bool = False
    fault_elem: int = 0
    state: int = 0
    ftq_flag: int = 0
    ftq_value: int = 0
    ftq_offset: int = 0
    lq_flag: int = 0
    lq_value: int = 0
    sq_first_flag: int = 0
    sq_second_flag: int = 0
    sq_value: int = 0
    pdest_valid: bool = True
    ordered_can_proceed: bool = True

    @property
    def is_load(self):
        return not (self.uop_type & 1)

    @property
    def is_ordered(self):
        return bool(self.uop_type & 2)

    @property
    def is_ordered_load(self):
        return self.is_ordered and self.is_load


@dataclass(frozen=True, slots=True)
class Redirect:
    valid: bool = False
    level: int = 0
    rob_flag: int = 0
    rob_value: int = 0


@dataclass(frozen=True, slots=True)
class Elem:
    idx_offset: int = 0
    byte_offset: int = 0
    sent_update: int = 0
    data_mask: int = 0
    data_size: int = 0


@dataclass(frozen=True, slots=True)
class LsuReq:
    entry_idx: int
    rob_flag: int
    rob_value: int
    is_load: int
    lq_flag: int
    lq_value: int
    sq_first_flag: int
    sq_second_flag: int
    sq_value: int
    elem_idx: int
    data_size: int
    data_mask: int
    ftq_flag: int
    ftq_value: int
    ftq_offset: int
    byte_offset: int
    vaddr: int
    pdest: int


@dataclass(frozen=True, slots=True)
class EmptyReq:
    entry_idx: int
    rob_flag: int
    rob_value: int
    is_load: int
    lq_value: int
    sq_first_flag: int
    sq_second_flag: int
    sq_value: int
    issue_mask: int


@dataclass(frozen=True, slots=True)
class Update:
    valid: bool = False
    entry_oh: int = 0
    set_req_sent: int = 0


@dataclass(frozen=True, slots=True)
class ExcpUpdate:
    valid: bool = False
    entry_oh: int = 0
    excp_set: int = 0


@dataclass(frozen=True, slots=True)
class Beat:
    entries: tuple[Entry, ...] = (Entry(),) * 8
    redirect: Redirect = Redirect()
    older_matrix: tuple[tuple[bool, ...], ...] = tuple(
        tuple(False for _ in range(8)) for _ in range(8)
    )
    lsu_ready: tuple[bool, bool, bool] = (False, False, False)
    empty_ready: tuple[bool, bool] = (False, False)


@dataclass(frozen=True, slots=True)
class Observation:
    lsu: tuple[LsuReq | None, LsuReq | None, LsuReq | None]
    empty: tuple[EmptyReq | None, EmptyReq | None]
    update: tuple[Update, Update]
    excp: ExcpUpdate
