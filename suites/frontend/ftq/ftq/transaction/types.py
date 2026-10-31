"""FTQ typed transactions."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Mapping

from suites.frontend.ftq.resolve_queue.transaction.types import Branch

ADDRESS_LIMIT = 1 << 50


def _address(name: str, value: int) -> None:
    if type(value) is not int or not 0 <= value < ADDRESS_LIMIT:
        raise ValueError(f"{name}={value!r} outside the 50-bit virtual address domain")


@dataclass(frozen=True, slots=True)
class Prediction:
    start_pc: int
    taken: int = 1
    end_position: int = 3
    s2_override: int = 0
    s3_override: int = 0
    s2_ptr: int | None = None
    s3_ptr: int | None = None
    s2_flag: int = 0
    s3_flag: int = 0

    def __post_init__(self) -> None:
        _address("start_pc", self.start_pc)
        for name, value, limit in (("taken", self.taken, 1),
                                   ("end_position", self.end_position, 31),
                                   ("s2_override", self.s2_override, 1),
                                   ("s3_override", self.s3_override, 1),
                                   ("s2_flag", self.s2_flag, 1),
                                   ("s3_flag", self.s3_flag, 1)):
            if type(value) is not int or not 0 <= value <= limit:
                raise ValueError(f"{name}={value!r} outside 0..{limit}")
        for name, pointer in (("s2_ptr", self.s2_ptr), ("s3_ptr", self.s3_ptr)):
            if pointer is not None and not 0 <= pointer < 64:
                raise ValueError(f"{name}={pointer!r} outside 0..63")


@dataclass(frozen=True, slots=True)
class Meta:
    """s3 metadata write for one already-admitted FTQ entry."""

    index: int
    flag: int = 0
    fields: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0 <= self.index < 64 or self.flag not in (0, 1):
            raise ValueError(f"illegal FTQ identity: {self.flag}:{self.index}")
        for key, value in self.fields.items():
            if type(value) is not int or value < 0:
                raise ValueError(f"meta field {key}={value!r} must be nonnegative")


@dataclass(frozen=True, slots=True)
class BackendRedirect:
    index: int
    flag: int = 0
    pc: int = 0x8000_1000
    offset: int = 1
    is_rvc: int = 1
    taken: int = 1
    target: int = 0x8000_3000
    branch_type: int = 1
    ras_action: int = 0
    level: int = 1
    ipf: int = 0
    igpf: int = 0
    iaf: int = 0
    satp_flush: int = 0
    debug_ctrl: int = 0
    debug_memvio: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.index < 64 or self.flag not in (0, 1):
            raise ValueError(f"illegal FTQ identity: {self.flag}:{self.index}")
        _address("pc", self.pc)
        _address("target", self.target)
        limits = {"offset": 31, "is_rvc": 1, "taken": 1, "level": 1,
                  "branch_type": 3, "ras_action": 3, "ipf": 1, "igpf": 1,
                  "iaf": 1, "satp_flush": 1, "debug_ctrl": 1, "debug_memvio": 1}
        for name, limit in limits.items():
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= limit:
                raise ValueError(f"{name}={value!r} outside 0..{limit}")
        if sum((self.ipf, self.igpf, self.iaf)) > 1:
            raise ValueError("backend exception flags are at most one-hot")


@dataclass(frozen=True, slots=True)
class IfuRedirect:
    index: int
    flag: int = 0
    pc: int = 0x8000_1000
    offset: int = 1
    is_rvc: int = 1
    taken: int = 1
    target: int = 0x8000_4000
    branch_type: int = 1
    ras_action: int = 0
    can_train: int = 1

    def __post_init__(self) -> None:
        if not 0 <= self.index < 64 or self.flag not in (0, 1):
            raise ValueError(f"illegal FTQ identity: {self.flag}:{self.index}")
        _address("pc", self.pc)
        _address("target", self.target)
        for name, limit in (("offset", 31), ("is_rvc", 1), ("taken", 1),
                            ("branch_type", 3), ("ras_action", 3),
                            ("can_train", 1)):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= limit:
                raise ValueError(f"{name}={value!r} outside 0..{limit}")


@dataclass(frozen=True, slots=True)
class Consumers:
    prefetch: int = 0
    mainpipe: int = 0
    train: int = 0
    real_two_fetch: int = 0


@dataclass(frozen=True, slots=True)
class Owner:
    flag: int
    value: int


@dataclass(frozen=True, slots=True)
class Pointers:
    bpu: Owner
    pf: tuple[Owner, Owner]
    fetch: tuple[Owner, Owner]
    commit: Owner
    pnr: Owner


@dataclass(frozen=True, slots=True)
class PrefetchRequest:
    valid: bool
    start: int
    next_line: int
    set0: int
    set1: int
    cross_line: bool
    index: int
    index_flag: int
    backend_exception: int
    case: int
    req1_start: int
    req1_index: int


@dataclass(frozen=True, slots=True)
class FetchRequest:
    valid: bool
    req1_valid: bool
    start: int
    addr0: int
    addr1: int
    index: int
    index_flag: int
    taken: int
    end_position: int
    bank0: int
    bank1: int
    backend_exception: bool
    satp_flush: bool
    req1_index: int


@dataclass(frozen=True, slots=True)
class TrainingEntry:
    start_pc: int
    start_pc_vec: tuple[int, ...]
    branches: tuple[Branch, ...]
    meta_phr: int
    meta_ghr: int
    meta_common_valid: int


@dataclass(frozen=True, slots=True)
class PredictionSpec:
    """Producer-side entry description used by allocate()."""

    start_pc: int
    taken: int = 1
    end_position: int = 3
    meta: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PredictionOffer:
    ready: bool
    wen: bool
    index: int
    start_pc: int


@dataclass(frozen=True, slots=True)
class CommitEvent:
    ras_action: int
    meta_ssp: int
    meta_tosw_flag: int
    meta_tosw_value: int


@dataclass(frozen=True, slots=True)
class RedirectEvent:
    cfi_pc: int
    target: int
    taken: int
    branch_type: int
    ras_action: int
    meta_phr: int
    meta_ghr: int


@dataclass(frozen=True, slots=True)
class FlushEvent:
    s2_valid: bool
    s2_flag: int
    s2_value: int
    s3_valid: bool
    s3_flag: int
    s3_value: int
    redirect_flush: bool
    to_ifu_redirect: bool
    ifu_s3_flush: bool


@dataclass(frozen=True, slots=True)
class Topdown:
    reasons: Mapping[int, int]
    backend_redirect: int
    control_flow: int
    memory_violation: int
    tage_miss: int
    ittage_miss: int
    ras_miss: int


@dataclass(frozen=True, slots=True)
class Entry:
    start_pc: int
    taken: int
    end_position: int


@dataclass(frozen=True, slots=True)
class BackendWrite:
    wen: bool
    index: int
    start_pc: int
