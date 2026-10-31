"""Consistent recent PHR profiles for the generated Kunminghu-v3 DefaultConfig.

The aggregate follows PhrAllFoldedHistories' sorted (history, folded) tuples.
Each fold XORs chunks of the selected recent history, as PhrHelper does;
copying one integer into every port is only correct for the old low-four-bit
profiles. Keep this predictor-specific layout out of the generic framework.
"""

from __future__ import annotations

from suites.frontend.bpu.models.configuration import PHR_FOLDS, PHR_STORAGE_BITS


# Types.scala getFoldedHistoryInfoSet, top/Configs.scala DefaultConfig and
# history/phr/Bundles.scala: sortBy(_.asTuple). Width/count changes fail fast
# against bound ports. History lengths are a contract of this fixed build;
# they cannot be inferred from widths for arbitrary other configurations.
PHR_FOLD_LAYOUT = PHR_FOLDS


def validate_folded_history_layout(widths) -> None:
    actual = tuple(widths)
    expected = tuple(width for _, width in PHR_FOLD_LAYOUT)
    if actual != expected:
        raise ValueError(f"PHR fold layout differs from generated DefaultConfig: {actual}, expected {expected}")


def folded_history_values(recent_bits: int, count: int) -> tuple[dict[str, int], ...]:
    if not isinstance(recent_bits, int) or not 0 <= recent_bits < 1 << PHR_STORAGE_BITS:
        raise ValueError(f"recent path history must fit {PHR_STORAGE_BITS} bits")
    if count != len(PHR_FOLD_LAYOUT):
        raise ValueError(f"PHR profile needs {len(PHR_FOLD_LAYOUT)} folds, got {count}")
    values = []
    for history_length, width in PHR_FOLD_LAYOUT:
        remaining = recent_bits & ((1 << history_length) - 1)
        folded = 0
        while remaining:
            folded ^= remaining & ((1 << width) - 1)
            remaining >>= width
        values.append({"foldedHist": folded})
    return tuple(values)
