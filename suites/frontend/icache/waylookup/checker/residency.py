"""Check way-lookup residency and read ordering against the reference model."""

from __future__ import annotations

from suites.frontend.icache.waylookup.model.queue import WayLookupModel
from suites.frontend.icache.waylookup.transaction.types import WayLookupRead


class ResidencyChecker:
    """Compare predicted residency and read beats with observed ones.

    Failures raise immediately: the queue is small and every cycle carries
    meaning, so an asynchronous scoreboard would only hide the first
    divergence point.
    """

    def __init__(self, model: WayLookupModel) -> None:
        self.model = model
        self.reads = 0
        self.idle_cycles = 0

    def expect_read(
        self,
        *,
        observed: WayLookupRead | None,
        expected_tag: int | None,
        context: str,
    ) -> None:
        predicted_valid = int(bool(self.model.tags))
        actual_valid = int(observed is not None)
        if actual_valid != predicted_valid:
            raise AssertionError(
                f"{context}: read fire {actual_valid} != predicted {predicted_valid}"
            )
        if observed is not None and expected_tag is not None:
            if observed.entry.ptag != expected_tag:
                raise AssertionError(
                    f"{context}: read pTag {observed.entry.ptag:#x} != expected {expected_tag:#x}"
                )
        self.reads += 1

    def expect_empty(self, *, observed: int, context: str) -> None:
        predicted = self.model.empty()
        if observed != predicted:
            raise AssertionError(
                f"{context}: perf.empty {observed} != predicted {predicted}"
            )
        self.idle_cycles += 1
