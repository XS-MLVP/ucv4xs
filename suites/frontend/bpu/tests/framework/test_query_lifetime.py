"""Independent source-stage replay, wrong-age association and credit controls."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from bpuverify.common.model.query_reset_program import Program, MODES
from bpuverify.common.model.query_lifetime import QueryLease

def test_equal_pc_and_equal_payload_cannot_replace_original_snapshot_identity():
    source = SimpleNamespace(pc=1073743872, position=2, target=1073746484)
    clone = deepcopy(source)
    lease = QueryLease()
    assert source == clone and source is not clone
    assert not lease.response(clone, 8)
    lease.accept(source, 10)
    assert not lease.response(clone, 12)
    assert lease.disposition is None
    assert lease.response(source, 12)
    lease.reset(14)
    assert lease.disposition == 'responded'

@pytest.mark.parametrize('fault', ('empty-source', 'duplicate-source', 'reset-without-source', 'reset-before-source', 'reset-at-source', 'response-before-source', 'duplicate-response', 'response-after-reset', 'duplicate-reset'))
def test_illegal_or_wrong_epoch_response_transitions_are_rejected(fault):
    source = SimpleNamespace(pc=1073743872)
    lease = QueryLease()
    if fault == 'reset-without-source':
        with pytest.raises(AssertionError):
            lease.reset(12)
        return
    if fault == 'empty-source':
        with pytest.raises(AssertionError):
            lease.accept(None, 10)
        return
    lease.accept(source, 10)
    if fault == 'duplicate-source':
        with pytest.raises(AssertionError):
            lease.accept(source, 12)
    elif fault in ('reset-before-source', 'reset-at-source'):
        with pytest.raises(AssertionError):
            lease.reset(8 if fault == 'reset-before-source' else 10)
    elif fault == 'response-before-source':
        with pytest.raises(AssertionError):
            lease.response(source, 8)
    elif fault == 'duplicate-response':
        assert lease.response(source, 12)
        with pytest.raises(AssertionError):
            lease.response(source, 14)
    elif fault == 'response-after-reset':
        lease.reset(12)
        with pytest.raises(AssertionError):
            lease.response(source, 14)
    else:
        lease.reset(12)
        with pytest.raises(AssertionError):
            lease.reset(14)

@pytest.mark.parametrize('dut,mode', (('tage', MODES[0]), ('', MODES[0]), (None, MODES[0]), (True, MODES[0]), ('mbtb', 'cold-only'), ('mbtb', None), ('mbtb', True)))
def test_unqualified_program_is_rejected(dut, mode):
    with pytest.raises(ValueError):
        Program(dut, mode)
