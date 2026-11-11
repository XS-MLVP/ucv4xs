"""Declared model geometry and actual public projection; not full table proof."""
import json
from pathlib import Path
import sys

import pytest

from suites.frontend.bpu.testbenches.bpu.model.configuration import MAIN_WAYS
from suites.frontend.bpu.testbenches.bpu.model.configuration import MICRO_HISTORIES
from suites.frontend.bpu.testbenches.bpu.model.configuration import SC_TABLES
from suites.frontend.bpu.testbenches.bpu.model.configuration import TAGE_HISTORIES

pytestmark = pytest.mark.selftest


def test_model_geometry_is_the_reviewed_defaultconfig_not_minimalconfig():
    assert MAIN_WAYS == 4
    assert MICRO_HISTORIES == (5, 9)
    assert len(TAGE_HISTORIES) == 8 and TAGE_HISTORIES[-1] == 397
    assert SC_TABLES == 8


async def test_generated_bpu_schema_is_checked_for_dce_and_consumed_shape(bpu_agent):
    schema = Path(sys.modules[type(bpu_agent.dut).__module__].__file__).with_name('signals.json')
    tree = json.loads(schema.read_text())['io']['toFtq']
    assert set(tree['prediction']['bits']) == {
        'startPc_addr', 'taken', 'endPosition', 's2Override', 's3Override'
    }
    assert 'perfMeta' not in tree
    assert not bpu_agent.ports.prediction_target_observable
    assert not bpu_agent.ports.meta_perf_observable
    main = tree['meta']['bits']['resolveMeta']['mbtb_entries']
    assert set(main) == {'0', '1'}
    assert all(set(bank) == set(map(str, range(MAIN_WAYS + 1))) for bank in main.values())
