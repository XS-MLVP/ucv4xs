"""Consistent recent PHR profiles for the generated Kunminghu-v3 MinimalConfig.

The aggregate follows PhrAllFoldedHistories' sorted (history, folded) tuples.
Each fold XORs chunks of the selected recent history, as PhrHelper does;
copying one integer into every port is only correct for the old low-four-bit
profiles. Keep this predictor-specific layout out of the generic framework.
"""

from __future__ import annotations


# Types.scala getFoldedHistoryInfoSet, top/Configs.scala MinimalConfig and
# history/phr/Bundles.scala: sortBy(_.asTuple). Width/count changes fail fast
# against bound ports. History lengths are a contract of this fixed build;
# they cannot be inferred from widths for arbitrary other configurations.
PHR_FOLD_LAYOUT = (
    (4, 4), (6, 5), (6, 6), (8, 6), (8, 7), (9, 7), (9, 9),
    (12, 5), (12, 6), (12, 9), (16, 6), (16, 7), (16, 8),
    (17, 7), (17, 12), (17, 13), (31, 7), (31, 12), (31, 13),
)


def validate_folded_history_layout(widths) -> None:
    actual = tuple(widths)
    expected = tuple(width for _, width in PHR_FOLD_LAYOUT)
    if actual != expected:
        raise ValueError(f"PHR fold layout differs from generated MinimalConfig: {actual}, expected {expected}")


def folded_history_values(recent_bits: int, count: int) -> tuple[dict[str, int], ...]:
    if not isinstance(recent_bits, int) or not 0 <= recent_bits < 1 << 31:
        raise ValueError("recent path history must fit 31 bits")
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
