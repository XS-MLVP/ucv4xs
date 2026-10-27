"""Subset feedback must not couple independent learning owners."""
from bpuverify.bpu.coverage.retouch_replacement import RetouchReplacementCoverage
from bpuverify.bpu.model.tage.owner_recency import PROGRAMS


class OwnerRecencyCoverage(RetouchReplacementCoverage):
    programs=PROGRAMS
    namespace='owner-recency'
    filename='functional-coverage-owner-recency.json'
