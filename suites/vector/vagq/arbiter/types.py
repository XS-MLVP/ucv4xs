"""Compact semantic packets for the combinational VAGQArbiter contract."""
from dataclasses import dataclass


ACTIVE_LANES = 3
LOAD_LANES = 3
STORE_LANES = 2
STD_LANES = 2


@dataclass(frozen=True, slots=True)
class NativeReq:
    valid: bool = False
    fields: tuple[tuple[str, int], ...] = ()

    @classmethod
    def from_dict(cls, valid=False, **fields):
        return cls(bool(valid), tuple(sorted((key, int(value)) for key, value in fields.items())))

    def values(self):
        return dict(self.fields)

    def get(self, name, default=0):
        return dict(self.fields).get(name, default)


@dataclass(frozen=True, slots=True)
class LsuReq:
    valid: bool = False
    entry_idx: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    is_load: bool = True
    lq_flag: int = 0
    lq_value: int = 0
    sq_first_flag: int = 0
    sq_second_flag: int = 0
    sq_value: int = 0
    elem_idx: int = 0
    data_size: int = 0
    data_mask: int = 0
    pc: int = 0
    ftq_flag: int = 0
    ftq_value: int = 0
    ftq_offset: int = 0
    byte_offset: int = 0
    vaddr: int = 0
    pdest: int = 0
    nf: int = 0


@dataclass(frozen=True, slots=True)
class StoreDataReq:
    valid: bool = False
    sq_first_flag: int = 0
    sq_second_flag: int = 0
    sq_value: int = 0
    data: int = 0


@dataclass(frozen=True, slots=True)
class Beat:
    vagq_lsu: tuple[LsuReq, LsuReq, LsuReq] = (LsuReq(), LsuReq(), LsuReq())
    vagq_store_data: tuple[StoreDataReq, StoreDataReq] = (StoreDataReq(), StoreDataReq())
    issue_lda: tuple[NativeReq, NativeReq, NativeReq] = (NativeReq(), NativeReq(), NativeReq())
    issue_sta: tuple[NativeReq, NativeReq] = (NativeReq(), NativeReq())
    ldu_ready: tuple[bool, bool, bool] = (False, False, False)
    sta_ready: tuple[bool, bool] = (False, False)
    std_busy: tuple[bool, bool] = (False, False)


@dataclass(frozen=True, slots=True)
class Observation:
    outputs: dict[str, int]
    load_grants: tuple[int | None, int | None, int | None]
    store_grants: tuple[int | None, int | None]
