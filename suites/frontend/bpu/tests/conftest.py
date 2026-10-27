from __future__ import annotations

from bpuverify.common.env.fixtures import dut_factory


pytest_plugins = ('bpuverify.common.pytest.runtime', 'bpuverify.common.pytest.features',
                  'bpuverify.common.pytest.artifacts', 'bpuverify.common.pytest.regression',
                  'bpuverify.common.pytest.isolation')
