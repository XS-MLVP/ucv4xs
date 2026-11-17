"""Transactions owned by ptwfilter."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Req:
    vpn: int
    s2xlate: int = 0
    get_gpa: int = 0
