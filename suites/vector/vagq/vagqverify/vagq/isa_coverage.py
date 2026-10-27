"""Behavior-level coverage for the RVV VAGQ audit.

The bins describe semantic obligations, not raw input encodings.  A sample may
be marked as a DUT counterexample; reaching a bin is never treated as proof by
itself.  The audit report keeps this coverage separate from the old public
contract group.
"""
from toffee import Bin, CrossDef, CoverGroupDef, CoverPointDef

from .scenario_matrix import (
    PUBLIC_DIMENSIONS,
    feature_case_id,
    feature_values,
    legal_public_feature_cases,
    public_space_metadata,
    representative_public_feature_cases,
)


class ISAAuditCoverage:
    def __init__(self, scope='public_dut', include_boundary=False):
        operations = (
            'strided-load', 'strided-store',
            'indexed-unordered-load', 'indexed-unordered-store',
            'indexed-ordered-load', 'indexed-ordered-store',
        )
        outcomes = ('dut-pass', 'dut-counterexample')
        ordering = ('unordered', 'ordered-load', 'ordered-store')
        if include_boundary:
            operations += ('unit-stride-outside-vagq',)
            outcomes += ('interface-gap', 'system-scope')
            ordering += ('ordered-segment-field-reorder',)
        self.group = CoverGroupDef('vagq_rvv_isa_audit_v1', (
            CoverPointDef('operation', {
                name: Bin.values(name) for name in operations
            }),
            CoverPointDef('lmul', {
                name: Bin.values(name) for name in (
                    'mf8', 'mf4', 'mf2', 'm1', 'm2', 'm4', 'm8',
                )
            }),
            CoverPointDef('data_eew', {
                name: Bin.values(name) for name in ('e8', 'e16', 'e32', 'e64')
            }),
            CoverPointDef('index_eew', {
                name: Bin.values(name) for name in ('e8', 'e16', 'e32', 'e64', 'na')
            }),
            CoverPointDef('element_window', {
                name: Bin.values(name) for name in (
                    'active', 'prestart', 'inactive', 'tail', 'vstart-ge-vl',
                )
            }),
            CoverPointDef('segment_mop', {
                name: Bin.values(name) for name in (
                    'non-segment', 'segment-narrow', 'segment-cross-flow',
                    'nonzero-start-field', 'full-uop-union',
                )
            }),
            CoverPointDef('address_boundary', {
                name: Bin.values(name) for name in (
                    'stride-negative', 'stride-zero', 'stride-positive',
                    'index-zero-extended', 'xlEN-wrap',
                )
            }),
            CoverPointDef('ordering', {
                name: Bin.values(name) for name in ordering
            }),
            CoverPointDef('restart_protocol', {
                name: Bin.values(name) for name in (
                    'normal', 'nack-retry', 'load-exception-restart',
                    'store-exception', 'redirect', 'backpressure',
                )
            }),
            CoverPointDef('audit_outcome', {
                name: Bin.values(name) for name in outcomes
            }),
        )).instantiate(
            f'vagq.rvv_isa_audit.{scope}.checked',
            contract=f'RVV v1.0 architectural memory semantics at VAGQ {scope} boundary/v1',
        )

    def sample(self, **values):
        required = {
            'operation', 'lmul', 'data_eew', 'index_eew', 'element_window',
            'segment_mop', 'address_boundary', 'ordering', 'restart_protocol',
            'audit_outcome',
        }
        missing = required - values.keys()
        if missing:
            raise ValueError(f'missing ISA coverage dimensions: {sorted(missing)}')
        self.group.sample({key: values[key] for key in required})


class PublicFeatureCoverage:
    """Coverage for the generated-DUT parameter-space campaign.

    This is intentionally separate from the semantic audit group: a feature
    shape being executed is not itself a proof that its address/MOP behavior is
    legal.  The test records the independent comparison outcome in the same
    sample so the report cannot hide a counterexample behind parameter bins.
    """
    def __init__(self):
        representative = tuple(representative_public_feature_cases())
        shape_bins = {
            feature_case_id(case): Bin.values(feature_case_id(case))
            for case in representative
        }
        # The audit contains a few deliberate boundary samples outside the
        # pairwise execution plan.  Keep them visible without pretending they
        # are one of the selected shape identities.
        shape_bins['supplemental'] = Bin.values('supplemental')
        point_bins = {
            'operation': ('strided-load', 'strided-store',
                          'indexed-unordered-load', 'indexed-unordered-store',
                          'indexed-ordered-load', 'indexed-ordered-store'),
            'vsew': ('e8', 'e16', 'e32', 'e64'),
            'vlmul': ('mf8', 'mf4', 'mf2', 'm1', 'm2', 'm4', 'm8'),
            'data_eew': ('e8', 'e16', 'e32', 'e64'),
            'index_eew': ('e8', 'e16', 'e32', 'e64', 'na'),
            'nf': tuple(str(index) for index in range(8)),
            'uop_count': tuple(str(index) for index in range(1, 9)),
            'comparison': ('pass', 'counterexample'),
        }
        points = [
            CoverPointDef(name, {
                value: Bin.values(value) for value in values
            })
            for name, values in point_bins.items()
        ]
        points.append(CoverPointDef('shape', shape_bins))

        legal = tuple(legal_public_feature_cases())
        crosses = []
        for offset, left in enumerate(PUBLIC_DIMENSIONS):
            for right in PUBLIC_DIMENSIONS[offset + 1:]:
                include = tuple(sorted({
                    (feature_values(case)[left], feature_values(case)[right])
                    for case in legal
                }))
                crosses.append(CrossDef(
                    f'{left}_x_{right}',
                    (left, right),
                    include=include,
                    description=(
                        'Legal RVV/public-boundary pairwise combinations; '
                        'reserved EMUL and >8-flow shapes are absent.'
                    ),
                ))
        self.group = CoverGroupDef('vagq_rvv_public_feature_space_v1', (
            *points,
        ), crosses=tuple(crosses)).instantiate(
            'vagq.rvv_isa_audit.public_dut.feature_space',
            contract='Independent RVV public feature-shape execution matrix/v2',
            run_metadata=public_space_metadata(),
        )

    def sample(self, *, operation, vsew, vlmul, data_eew, index_eew,
               nf, uop_count, comparison, shape_id='supplemental'):
        self.group.sample({
            'operation': operation,
            'vsew': vsew,
            'vlmul': vlmul,
            'data_eew': data_eew,
            'index_eew': index_eew,
            'nf': nf,
            'uop_count': uop_count,
            'comparison': comparison,
            'shape': shape_id,
        })


# One shared instance keeps samples from the separate real-root probe files in
# the same managed toffee functional group.  Boundary-only evidence uses a
# different scope and is never silently combined with public-DUT coverage.
DUT_COVERAGE = ISAAuditCoverage()
BOUNDARY_COVERAGE = ISAAuditCoverage(scope='boundary', include_boundary=True)
PUBLIC_FEATURE_COVERAGE = PublicFeatureCoverage()
