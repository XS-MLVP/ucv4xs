from __future__ import annotations

from icacheverify.common.env.fixtures import dut_factory


pytest_plugins = ('icacheverify.common.pytest.runtime', 'icacheverify.common.pytest.features',
                  'icacheverify.common.pytest.artifacts', 'icacheverify.common.pytest.regression')
