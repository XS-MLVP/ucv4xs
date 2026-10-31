"""Immutable evidence of a positive entry learned from an original source."""
from dataclasses import dataclass


@dataclass(frozen=True,slots=True)
class PositiveSeed:
    owner: object
    snapshot: object
    key: tuple[int,int]
    entry: object
    useful: int
    written: int
    compared: int | None = None
