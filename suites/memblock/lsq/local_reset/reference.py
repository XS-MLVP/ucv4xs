"""Explicit external-ledger-only retention; shared reset/outputs unchanged."""
from suites.memblock.lsq.lsq_wrapper.model import WrapperModel


class RetainedExternalLoadJobs(WrapperModel):
    def advance(self, inp):
        retained={uid:dict(job) for uid,job in self.jobs.items()} if inp.reset else None
        if retained:
            assert all(job["kind"]=="load" and job["sid"] is not None for job in retained.values()), "this opt-in profile retains only already-acked external Load jobs"
            assert self.serial is None, "this batch uses NC outstanding, not retained local serial arbitration"
        change=super().advance(inp)
        if inp.reset:
            assert self.serial is None and not self.jobs
            self.jobs=retained
            change["external_bus_jobs"]={uid:dict(job) for uid,job in retained.items()}
            change["local_reset_external_jobs_retained_not_aborted"]=len(retained)
        return change
