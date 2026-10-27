from toffee import Bin, CoverGroupDef, CoverPointDef

from lsqverify.native import ROOT

SCENARIOS = {}
for line in (ROOT / "docs/contracts/lsq-wrapper.md").read_text().splitlines():
    if line.startswith("| LSQ-"):
        _, group, cases, meaning, _ = line.split("|")
        for case in cases.split("/"):
            SCENARIOS[group.strip() + "." + case.strip()] = meaning.strip()
assert len(SCENARIOS) == 82


class FunctionalCoverage:
    def __init__(self, nodeid):
        point = CoverPointDef("scenario", {key: Bin.values(key) for key in SCENARIOS},
                              description="; ".join(key + ": " + value for key, value in SCENARIOS.items()))
        groups = {}
        for stage in ("reached", "checked"):
            groups[stage] = CoverGroupDef("lsq.wrapper." + stage, (point,)).instantiate("lsq.lsq_wrapper." + stage,
                            run_metadata={"dut": "lsq_wrapper", "test": nodeid}, contract="real-mixed-load-store." + stage + "/v1")
        self.groups = groups

    def sample(self, names, tick, *, checked=False):
        for name in names:
            assert name in SCENARIOS
            self.groups["checked" if checked else "reached"].sample({"scenario": name}, metadata={"tick": tick}, details=False)
