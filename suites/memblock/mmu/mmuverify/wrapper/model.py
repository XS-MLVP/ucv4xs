"""Tree-PLRU and wrapper-level model for TlbStorageWrapper.

The replacement model mirrors the recursive PseudoLRU implementation used by
the generated wrapper. It is kept independent of RTL and is used to predict
which way a refill overwrites.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..tlbfa.model import (
    ALL_STAGE,
    Context,
    ExpectedResponse,
    Refill,
    TlbfaModel,
    WAYS,
)


def _ceil_log2(value: int) -> int:
    return max(1, (value - 1).bit_length())


def _extract(value: int, high: int, low: int) -> int:
    if high < low:
        return 0
    return (value >> low) & ((1 << (high - low + 1)) - 1)


def _concat(*parts: tuple[int, int]) -> int:
    result = 0
    for value, width in parts:
        result = (result << width) | (value & ((1 << width) - 1))
    return result


class PseudoLRU:
    def __init__(self, ways: int = WAYS) -> None:
        self.ways = ways
        self.state = 0

    def reset(self) -> None:
        self.state = 0

    @property
    def width(self) -> int:
        return self.ways - 1

    def victim(self) -> int:
        return self._replace(self.state, self.ways)

    def access(self, way: int) -> None:
        self.state = self._next(self.state, way, self.ways)

    def _replace(self, state: int, n: int) -> int:
        if n > 2:
            right_n = 1 << (_ceil_log2(n) - 1)
            left_n = n - right_n
            left_older = (state >> (n - 2)) & 1
            left_state = _extract(state, n - 3, right_n - 1)
            right_state = _extract(state, right_n - 2, 0)
            if left_n > 1:
                sub = (
                    self._replace(left_state, left_n)
                    if left_older
                    else self._replace(right_state, right_n)
                )
            else:
                sub = 0 if left_older else self._replace(right_state, right_n)
            return (left_older << (_ceil_log2(n) - 1)) | sub
        if n == 2:
            return state & 1
        return 0

    def _next(self, state: int, touch: int, n: int) -> int:
        if n > 2:
            right_n = 1 << (_ceil_log2(n) - 1)
            left_n = n - right_n
            set_left_older = 0 if ((touch >> (_ceil_log2(n) - 1)) & 1) else 1
            left_state = _extract(state, n - 3, right_n - 1)
            right_state = _extract(state, right_n - 2, 0)
            if left_n > 1:
                left_new = (
                    left_state
                    if set_left_older
                    else self._next(
                        left_state,
                        _extract(touch, _ceil_log2(left_n) - 1, 0),
                        left_n,
                    )
                )
                right_new = (
                    self._next(
                        right_state,
                        _extract(touch, _ceil_log2(right_n) - 1, 0),
                        right_n,
                    )
                    if set_left_older
                    else right_state
                )
                return _concat(
                    (set_left_older, 1),
                    (left_new, left_n - 1),
                    (right_new, right_n - 1),
                )
            right_new = (
                self._next(
                    right_state,
                    _extract(touch, _ceil_log2(right_n) - 1, 0),
                    right_n,
                )
                if set_left_older
                else right_state
            )
            return _concat((set_left_older, 1), (right_new, right_n - 1))
        if n == 2:
            return 0 if (touch & 1) else 1
        return 0


@dataclass
class WrapperRefillResult:
    way: int


class WrapperModel:
    def __init__(self) -> None:
        self.tlbfa = TlbfaModel()
        self.plru = PseudoLRU(WAYS)
        self.last_refill_way: int | None = None
        self.last_lookup_hit_way: int | None = None

    @property
    def context(self) -> Context:
        return self.tlbfa.context

    def reset(self) -> None:
        self.tlbfa.reset()
        self.plru.reset()
        self.last_refill_way = None
        self.last_lookup_hit_way = None

    def victim(self) -> int:
        return self.plru.victim()

    def refill(self, data: Refill) -> int:
        way = self.plru.victim()
        self.tlbfa.refill(way, data)
        self.plru.access(way)
        self.last_refill_way = way
        return way

    def lookup(self, vpn: int, s2xlate: int) -> ExpectedResponse:
        expected = self.tlbfa.lookup(vpn, s2xlate)
        if expected.hit and expected.way is not None:
            self.plru.access(expected.way)
            self.last_lookup_hit_way = expected.way
        return expected

    def hit_ways(self, vpn: int, s2xlate: int) -> list[int]:
        return self.tlbfa.hit_ways(vpn, s2xlate)

    def live_tags(self, kind_pairs: list[tuple[int, int]]) -> list[int]:
        """Return indices of (vpn, s2xlate) pairs that still hit."""
        return [
            index
            for index, (vpn, s2xlate) in enumerate(kind_pairs)
            if self.tlbfa.hit_ways(vpn, s2xlate)
        ]
