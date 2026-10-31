"""Small semantic checks with explicit expectations, never DUT-derived answers."""


def check_l2_success(snap, *, ppn=None, tag=None, stage=None):
    required = {"valid", "s2xlate", "s1_v", "s1_pf", "s1_af", "s1_ppn", "s1_tag"}
    assert required <= snap.keys(), ("missing response fields", required - snap.keys())
    assert snap["valid"] == 1, snap
    if stage is not None:
        assert snap["s2xlate"] == stage, snap
    if snap["s2xlate"] != 2:
        assert snap["s1_v"] == 1 and snap["s1_pf"] == 0 and snap["s1_af"] == 0, snap
        if ppn is not None:
            assert snap["s1_ppn"] == ppn, snap
        if tag is not None:
            assert snap["s1_tag"] == tag, snap
    if snap["s2xlate"] in (2, 3):
        assert {"s2_gpf", "s2_gaf"} <= snap.keys(), snap
        assert snap["s2_gpf"] == 0 and snap["s2_gaf"] == 0, snap
