"""Small domain packets for EntryTable's observable lifecycle."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AddrPacket:
    entry_idx: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    uop_type: int = 0
    meta_ftq_flag: int = 0
    meta_ftq_value: int = 0
    meta_ftq_offset: int = 0
    meta_lq_flag: int = 0
    meta_lq_value: int = 0
    meta_sq_first_flag: int = 0
    meta_sq_second_flag: int = 0
    meta_sq_value: int = 0
    meta_vsew: int = 0
    meta_vlmul: int = 0
    pdest: int = 0
    psrc2: int = 0
    base_addr: int = 0
    v0_mask: int = 0xffff
    deew: int = 0
    ieew: int = 0
    emul: int = 0
    vl: int = 16
    vstart: int = 0
    vma: int = 0
    vta: int = 0
    uop_idx: int = 0
    last_uop: int = 0
    nf: int = 0


@dataclass(frozen=True, slots=True)
class DataPacket:
    entry_idx: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    op2_data: int = 0


@dataclass(frozen=True, slots=True)
class StateUpdate:
    valid: bool = False
    entry_oh: int = 0
    state_next: int = 0


@dataclass(frozen=True, slots=True)
class SplitReq:
    valid: bool = False
    entry_oh: int = 0
    set_req_sent: int = 0


@dataclass(frozen=True, slots=True)
class MergeResp:
    entry_oh: int = 0
    set_req_ack: int = 0
    clear_req_sent: int = 0
    exception: bool = False
    exception_number: int = 0
    fault_elem_idx: int = 0


@dataclass(frozen=True, slots=True)
class StoreUpdate:
    valid: bool = False
    entry_idx: int = 0
    set_data_sent: int = 0


@dataclass(frozen=True, slots=True)
class ExcpUpdate:
    valid: bool = False
    entry_oh: int = 0
    excp_set: int = 0


@dataclass(frozen=True, slots=True)
class Redirect:
    valid: bool = False
    level: int = 0
    rob_flag: int = 0
    rob_value: int = 0


@dataclass(frozen=True, slots=True)
class Beat:
    addr: tuple[AddrPacket | None, AddrPacket | None] = (None, None)
    addr_valid: tuple[bool, bool] = (False, False)
    data: tuple[DataPacket | None, DataPacket | None] = (None, None)
    data_valid: tuple[bool, bool] = (False, False)
    index: tuple[DataPacket | None, DataPacket | None] = (None, None)
    index_valid: tuple[bool, bool] = (False, False)
    split_req: tuple[SplitReq, SplitReq] = (SplitReq(), SplitReq())
    merge_resp: tuple[MergeResp, ...] = (MergeResp(),) * 7
    split_done: StateUpdate = StateUpdate()
    merge_done: StateUpdate = StateUpdate()
    rob_clear: StateUpdate = StateUpdate()
    store_update: tuple[StoreUpdate, StoreUpdate] = (StoreUpdate(), StoreUpdate())
    excp_update: ExcpUpdate = ExcpUpdate()
    redirect: Redirect = Redirect()
