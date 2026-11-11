"""Source-qualified integrated behavior, distinct from UT free-index programs."""
import json
from pathlib import Path
from suites.frontend.bpu.testbenches.bpu.model.neutral_recovery import PROFILES
from suites.frontend.bpu.testbenches.bpu.model.neutral_recovery import rules
from suites.frontend.bpu.testbenches.bpu.coverage.neutral_recovery import lifetime_coverage


def test_requirement_has_real_integrated_sources_and_preserves_native_gaps():
    contract = json.loads(Path('docs/spec/verification/contracts/bpu-neutral-recovery-contract.json').read_text())
    assert contract['existing_feature'] == 'BPU-INT-066' and contract['new_feature_IDs'] == 0
    assert contract['profiles'] == list(PROFILES)
    assert contract['gap_basis']['integrated_low_region_native_zero_rows'] == 515
    assert 'S1' in contract['owner'] and 'S3' in contract['owner']
    assert contract['no_bank_set_way_enumeration'] and contract['no_fixed_native_settling_delay']
    for ref in contract['source_chain']:
        name, line = ref.rsplit(':', 1)
        assert 0 < int(line) <= len(Path(name).read_text().splitlines())


def test_schema_is_the_two_semantic_chains_not_physical_locations():
    for status in ('reached', 'checked'):
        counts = lifetime_coverage(status).report()['points'][0]['counts']
        assert len(counts) == sum(len(rules(p)) for p in PROFILES) == 39
        assert set(counts.values()) == {0}
