"""Transactions owned by bitmap."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BmReq:
    bmppn: int
    vpn: int = 0
    level: int = 0
    n: int = 0
    s2xlate: int = 0
    way_info: int = 0
    hptw_bypassed: int = 0
    id: int = 0
