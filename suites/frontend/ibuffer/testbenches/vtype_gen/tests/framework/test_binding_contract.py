"""VTypeGen structural binding evidence."""

from __future__ import annotations

import pytest


@pytest.mark.feature("IBUF-ENV-001")
async def test_vtype_gen_binds_every_port(vtype_gen_agent):
    audit = vtype_gen_agent.audit()
    assert audit["top"] == "VTypeGen"
    assert audit["absent"] == {}
    assert len(audit["outputs"]) == 2 * 8 * 5
    # reset, 8*(valid,bits), walkToArch, walk valid, walk bits, canUpdate,
    # vsetvl bits, commit valid, commit bits, hasVsetvl.
    assert len(audit["inputs"]) == 1 + 8 * 2 + 1 + 1 + 5 + 1 + 5 + 1 + 5 + 1
    assert "can_update_vtype" in audit["inputs"]
    assert "specvtype_7_vlmul" in audit["outputs"]
