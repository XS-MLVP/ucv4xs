"""Subset feedback must not couple independent learning owners."""
from suites.frontend.bpu.bpu.coverage.retouch_replacement import RetouchReplacementCoverage
from suites.frontend.bpu.bpu.model.tage.owner_recency import PROGRAMS


class OwnerRecencyCoverage(RetouchReplacementCoverage):
    programs=PROGRAMS
    namespace='owner-recency'
    filename='functional-coverage-owner-recency.json'
