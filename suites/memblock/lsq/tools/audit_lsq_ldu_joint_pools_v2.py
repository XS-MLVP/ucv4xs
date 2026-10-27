#!/usr/bin/env python3
"""Keep v1 semantic core; distinguish post-redirect same-pointer generations."""
from audit_lsq_ldu_joint_pools_v1 import PhasedPools as OriginalPools


class PhasedPools(OriginalPools):
    def step(self, row):
        if row["input"]["reset"]:
            return super().step(row)
        # The original key used epoch, SQ/LQ tails and kind. A full redirect
        # restores all three, so it merged two different original-UID peaks.
        # Independently generate the candidate, then dedup with public history
        # length as an extra generation discriminator. Inputs/pool logic stay.
        saved = self.snapshots
        self.snapshots = []
        super().step(row)
        candidates = self.snapshots
        self.snapshots = saved
        for candidate in candidates:
            candidate["key"] = (*candidate["key"],len(self.history))
            if not self.snapshots or self.snapshots[-1]["key"] != candidate["key"]:
                self.snapshots.append(candidate)

    def finish(self, *, passed):
        report = super().finish(passed=passed)
        counts = report["counts"]
        counts["failed_live"] = sum(self.live(s) for s in self.history)
        assert counts["allocated"] == counts["completed"]+counts["cancelled"]+counts["reset_aborted"]+counts["failed_live"]
        report["preserved_v1_limit"] = "v1 merged same-pointer peaks after redirect; v2 adds actual public UID generation to snapshot dedup only and reports active terminal owners. All query/revoke/lease/bus/effect semantics, originals and native results unchanged."
        return report
