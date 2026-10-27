"""bpuverify.uras.transaction.types components."""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UrasCycle:
    enable: int = 1
    s1_fire: int = 0
    s2_fire: int = 0
    s3_fire: int = 0
    has_redirect: int = 0
    full_ret_addr: int = 0
    spec_action: int = 0
    spec_position: int = 0
    spec_start_pc: int = 0
    s2_valid: int = 0
    s2_action: int = 0
    s2_position: int = 0
    s2_start_pc: int = 0
    s3_valid: int = 0
    s3_action: int = 0
    s3_position: int = 0
    s3_start_pc: int = 0


@dataclass(frozen=True, slots=True)
class UrasResult:
    usable: int
    target: int
