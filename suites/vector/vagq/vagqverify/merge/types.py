"""Semantic MergeCtrl inputs, responses and public observations."""
from dataclasses import dataclass


NUM_ENTRIES = 8
SPLIT = 3
MERGE = 4
WB = 5
ALL_BYTES = 0xffff


@dataclass(frozen=True, slots=True)
class Entry:
    valid: bool = False
    uop_type: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    pdest: int = 0
    psrc2: int = 0
    deew: int = 0
    uop_idx: int = 0
    skip_merge: bool = False
    elem_active: int = 0
    merge_write: int = 0
    elem_agnostic: int = 0
    nf: int = 0
    req_ack: int = 0
    data_sent: int = 0
    exception: bool = False
    exception_number: int = 0
    fault_elem: int = 0
    state: int = 0
    ordered_can_proceed: bool = True
    lq_flag: int = 0
    lq_value: int = 0
    sq_first_flag: int = 0
    sq_second_flag: int = 0
    sq_value: int = 0
    vsew: int = 0
    vlmul: int = 0
    perf_eliminated: int = 0
    perf_rename: int = 0
    perf_dispatch: int = 0
    perf_enq_rs: int = 0
    perf_select: int = 0
    perf_issue: int = 0
    perf_runahead: int = 0
    perf_tlb_first: int = 0
    perf_tlb_resp: int = 0
    debug_seq_num: int = 0
    debug_uop_idx: int = 0

    @property
    def is_load(self):
        return not bool(self.uop_type & 1)

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
class Response:
    valid: bool = False
    entry_idx: int = 0
    issue_mask: int = 0
    is_nack: bool = False
    exception: bool = False
    exception_number: int = 0
    fault_elem: int = 0


@dataclass(frozen=True, slots=True)
class ResponseUpdate:
    set_req_ack: int = 0
    clear_req_sent: int = 0
    exception: bool = False
    exception_number: int = 0
    fault_elem: int = 0
    entry_hit_oh: int = 0


@dataclass(frozen=True, slots=True)
class VrfReadRequest:
    valid: bool = False
    entry_idx: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    psrc: int = 0


@dataclass(frozen=True, slots=True)
class VrfWriteRequest:
    valid: bool = False
    entry_idx: int = 0
    pdest: int = 0
    data: int = 0
    mask: int = 0


@dataclass(frozen=True, slots=True)
class StateUpdate:
    valid: bool = False
    entry_oh: int = 0
    state_next: int = 0


@dataclass(frozen=True, slots=True)
class RobWriteback:
    valid: bool = False
    entry_idx: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    exception: bool = False
    exception_number: int = 0
    fault_vstart: int = 0
    uop_type: int = 0
    uop_idx: int = 0
    deew: int = 0
    nf: int = 0
    lq_flag: int = 0
    lq_value: int = 0
    sq_first_flag: int = 0
    sq_second_flag: int = 0
    sq_value: int = 0
    trigger: int = 0
    vsew: int = 0
    vlmul: int = 0
    perf_eliminated: int = 0
    perf_rename: int = 0
    perf_dispatch: int = 0
    perf_enq_rs: int = 0
    perf_select: int = 0
    perf_issue: int = 0
    perf_runahead: int = 0
    perf_tlb_first: int = 0
    perf_tlb_resp: int = 0
    debug_seq_num: int = 0
    debug_uop_idx: int = 0


@dataclass(frozen=True, slots=True)
class Beat:
    entries: tuple[Entry, ...] = (Entry(),) * NUM_ENTRIES
    psrc2_ready: tuple[bool, ...] = (False,) * NUM_ENTRIES
    ldu_resp: tuple[Response, Response, Response] = (Response(),) * 3
    sta_resp: tuple[Response, Response] = (Response(),) * 2
    empty_resp: tuple[Response, Response] = (Response(),) * 2
    older_matrix: tuple[tuple[bool, ...], ...] = tuple(
        tuple(False for _ in range(NUM_ENTRIES)) for _ in range(NUM_ENTRIES)
    )
    vrf_read_req_ready: bool = False
    vrf_read_resp_valid: bool = False
    vrf_read_resp_entry_idx: int = 0
    vrf_read_resp_rob_flag: int = 0
    vrf_read_resp_rob_value: int = 0
    vrf_read_resp_data: int = 0
    redirect: Redirect = Redirect()


@dataclass(frozen=True, slots=True)
class Observation:
    updates: tuple[ResponseUpdate, ...]
    split_done: StateUpdate
    merge_done: StateUpdate
    rob_clear: StateUpdate
    vrf_read: VrfReadRequest
    vrf_write: VrfWriteRequest
    rob_writeback: RobWriteback
    vp_wakeup_valid: bool
    vp_wakeup: int
