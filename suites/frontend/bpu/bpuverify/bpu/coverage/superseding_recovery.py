"""Reached recovery stimulus and fully checked surviving-prefix programs."""
import json
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.model.superseding_recovery import PROFILES, RULES


def lifetime_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('recovery coverage requires reached or checked')
    return CoverGroupDef('superseding_recovery_v1', (
        CoverPointDef('obligation', {p+'.'+r: Bin.values(p+'.'+r) for p in PROFILES for r in RULES}),
    )).instantiate('kunminghu_v3.bpu.superseding-recovery.'+status,
        contract='two distinct real originals; younger then older adjacent recovery; only surviving original prefix is consumed')


class SupersedingRecoveryCoverage:
    def __init__(self):
        self.groups = {s: lifetime_coverage(s) for s in ('reached', 'checked')}
        self.evidence = None

    def record(self, status, profile, rule, **witness):
        if profile not in PROFILES or rule not in RULES:
            raise ValueError('undeclared recovery obligation')
        self.groups[status].sample(dict(obligation=profile+'.'+rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-superseding-recovery.json')

    def attach_evidence(self, properties):
        if self.evidence is not None:
            properties.append(('semantic_superseding_recovery', json.dumps(self.evidence, ensure_ascii=False)))
