#!/usr/bin/env python3
"""Public-UID snapshot discriminator without revalidating a peak during exit.

All original v1 pool/UID/request/revoke semantics remain unchanged. v2 forced
candidate generation every quiet edge and wrongly checked entry conditions
again while service was already leaving the same peak. Keep both versions.
"""
from audit_lsq_ldu_joint_pools_v1 import PhasedPools as OriginalPools


class PhasedPools(OriginalPools):
    def step(self, row):
        previous = self.snapshots[-1] if self.snapshots else None
        previous_key = previous["key"] if previous is not None else None
        before = len(self.snapshots)
        # Present v1's original four-field key only when it is still the SAME
        # original UID generation. Otherwise it must generate a new witness,
        # even if redirect restored all ROB/SQ/LQ pointer encodings.
        if previous is not None and len(previous_key) == 5 and previous_key[-1] == len(self.history):
            previous["key"] = previous_key[:4]
        try:
            super().step(row)
        finally:
            if previous is not None:previous["key"] = previous_key
        for candidate in self.snapshots[before:]:
            candidate["key"] = (*candidate["key"],len(self.history))

    def finish(self, *, passed):
        report = super().finish(passed=passed)
        counts = report["counts"]
        counts["failed_live"] = sum(self.live(s) for s in self.history)
        assert counts["allocated"] == counts["completed"]+counts["cancelled"]+counts["reset_aborted"]+counts["failed_live"]
        report["preserved_prior_auditor_limits"] = "v1 merged same-pointer post-redirect peaks; v2 forced revalidation during exit and rejected already-served first STA. v3 only distinguishes public UID generation while preserving v1 entry-only semantics. No source, input/output, pool rule, native result or original failure modified."
        return report
