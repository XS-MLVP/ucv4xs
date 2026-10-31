"""Pure scope/boundary records for the RVV VAGQ audit.

These samples are intentionally kept in a separate ``boundary`` coverage
instance.  They document semantics that are outside the VAGQ generated root
(for example unit-stride) or cannot be observed through its public leaves;
they never contribute to public-DUT coverage.
"""
import pytest

from suites.vector.vagq.vagq.isa_coverage import BOUNDARY_COVERAGE


pytestmark = pytest.mark.vagq_isa_audit


def _sample(**overrides):
    values = dict(
        operation='strided-load',
        lmul='m1',
        data_eew='e8',
        index_eew='na',
        element_window='active',
        segment_mop='non-segment',
        address_boundary='stride-zero',
        ordering='unordered',
        restart_protocol='normal',
        audit_outcome='system-scope',
    )
    values.update(overrides)
    BOUNDARY_COVERAGE.sample(**values)


def test_scope_and_unobservable_semantics_are_explicitly_recorded():
    for operation in (
        'strided-load', 'strided-store',
        'indexed-unordered-load', 'indexed-unordered-store',
        'indexed-ordered-load', 'indexed-ordered-store',
        'unit-stride-outside-vagq',
    ):
        _sample(
            operation=operation,
            index_eew='e8' if 'indexed' in operation else 'na',
            ordering=(
                'ordered-load' if operation == 'indexed-ordered-load' else
                'ordered-store' if operation == 'indexed-ordered-store' else
                'unordered'
            ),
        )
    for lmul in ('mf8', 'mf4', 'mf2', 'm1', 'm2', 'm4', 'm8'):
        _sample(lmul=lmul)
    for eew in ('e8', 'e16', 'e32', 'e64'):
        _sample(data_eew=eew)
        _sample(index_eew=eew, operation='indexed-unordered-load')
    for window in ('active', 'prestart', 'inactive', 'tail', 'vstart-ge-vl'):
        _sample(element_window=window)
    for segment in (
        'non-segment', 'segment-narrow', 'segment-cross-flow',
        'nonzero-start-field', 'full-uop-union',
    ):
        _sample(segment_mop=segment)
    for boundary in (
        'stride-negative', 'stride-zero', 'stride-positive',
        'index-zero-extended', 'xlEN-wrap',
    ):
        _sample(address_boundary=boundary)
    _sample(ordering='ordered-segment-field-reorder')
    for protocol in (
        'normal', 'nack-retry', 'load-exception-restart',
        'store-exception', 'redirect', 'backpressure',
    ):
        _sample(restart_protocol=protocol)
    for outcome in ('dut-pass', 'dut-counterexample', 'interface-gap', 'system-scope'):
        _sample(audit_outcome=outcome)
