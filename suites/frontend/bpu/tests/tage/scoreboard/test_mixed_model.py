"""Independent mixed-write payload and no-op/gating semantics."""
from types import SimpleNamespace

import pytest

from bpuverify.tage.model.mixed import expected_tage_mixed_writes
from bpuverify.tage.monitor.write import TageWriteActivityMonitor


@pytest.mark.parametrize('pc', (0x40000000, 0x40000020, 0x40000001, 0x40000400))
@pytest.mark.parametrize('way', (0, 1))
def test_mixed_payloads_derive_both_port_identities(pc, way):
    expected = expected_tage_mixed_writes(pc, 6, way, 2)
    assert expected['beats'] == 1 and expected['latency_ticks'] == 8
    ports = expected['banks'][pc & 3]
    assert ports[way] == {'set_idx': (pc >> 2) & 127, 'tag': ((pc >> 9) & 8191) ^ 6,
                          'counter': 1, 'entry_valid': 1, 'taken': 0}
    assert ports[1-way] == {'set_idx': (pc >> 2) & 127, 'tag': ((pc >> 9) & 8191) ^ 9,
                            'counter': 4, 'entry_valid': 1, 'taken': 1}
    assert all(bank == (None, None) for i, bank in enumerate(expected['banks']) if i != (pc & 3))


@pytest.mark.parametrize('counter, qualified, allocation', ((0, True, True), (1, False, True), (1, False, False)))
def test_hold_and_gate_do_not_fabricate_a_second_write(counter, qualified, allocation):
    expected = expected_tage_mixed_writes(0x40000000, 6, 0, counter, qualified=qualified, allocation=allocation)
    if allocation:
        assert expected['beats'] == 1 and expected['banks'][0][0] is None
        assert expected['banks'][0][1]['counter'] == 4
    else:
        assert expected == {'beats': 0}


@pytest.mark.parametrize('pc, pos, way, counter', ((-1, 6, 0, 1), (0, 6, 2, 1), (0, 6, 0, 3), (0, 9, 0, 1)))
def test_mixed_reference_rejects_out_of_scope_geometry(pc, pos, way, counter):
    with pytest.raises(ValueError):
        expected_tage_mixed_writes(pc, pos, way, counter)


def test_write_decoder_discards_inactive_port_payload():
    def word(value):
        return SimpleNamespace(as_int=lambda: value)

    active = SimpleNamespace(valid=word(1), set_idx=word(8), tag=word(9), counter=word(4),
                             entry_valid=word(1), taken=word(1))
    inactive = SimpleNamespace(valid=word(0))
    decoded = TageWriteActivityMonitor.decode(SimpleNamespace(banks=((inactive, active), (inactive, inactive))))
    assert decoded == {'banks': ((None, {'set_idx': 8, 'tag': 9, 'counter': 4, 'entry_valid': 1, 'taken': 1}),
                                (None, None))}
