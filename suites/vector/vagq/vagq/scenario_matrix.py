"""Independent, deterministic feature-space generation for the VAGQ campaign.

The inventory in this module is deliberately expressed in RVV/public-boundary
terms.  It does not import generated RTL lookup tables or the integration
model.  ``legal_public_feature_cases`` is the denominator inventory; the
representative set is a pairwise covering execution plan, not an assertion that
all legal shapes were run on the generated DUT.
"""
from dataclasses import dataclass
import hashlib
import json

from .isa_reference import emul_encoding, vlmax


PUBLIC_OPERATIONS = (0, 1, 4, 5, 6, 7)
LMUL_ENCODINGS = (5, 6, 7, 0, 1, 2, 3)
EEW_ENCODINGS = (0, 1, 2, 3)
PUBLIC_DIMENSIONS = (
    'operation', 'vsew', 'vlmul', 'data_eew', 'index_eew', 'nf', 'uop_count',
)

OPERATION_NAMES = {
    0: 'strided-load',
    1: 'strided-store',
    4: 'indexed-unordered-load',
    5: 'indexed-unordered-store',
    6: 'indexed-ordered-load',
    7: 'indexed-ordered-store',
}
VSEW_NAMES = {0: 'e8', 1: 'e16', 2: 'e32', 3: 'e64'}
LMUL_NAMES = {5: 'mf8', 6: 'mf4', 7: 'mf2', 0: 'm1', 1: 'm2', 2: 'm4', 3: 'm8'}
EEW_NAMES = VSEW_NAMES


@dataclass(frozen=True, slots=True)
class FeatureCase:
    operation: int
    vsew: int
    vlmul: int
    data_eew: int
    index_eew: int
    nf: int
    vlmax: int
    uop_count: int

    @property
    def indexed(self):
        return self.operation >= 4

    @property
    def ordered(self):
        return self.operation in (6, 7)

    @property
    def load(self):
        return (self.operation & 1) == 0


def legal_public_feature_cases(*, vlen_bits=128, flow_bytes=16):
    """Yield every representable public operand shape without using RTL tables.

    The generator is a campaign-space inventory, not a claim that every
    encoding is legal for every whole-chip decoder.  Reserved/non-representable
    EMUL and more-than-eight-flow shapes are excluded explicitly and counted by
    the pure tests.
    """
    for operation in PUBLIC_OPERATIONS:
        for vsew in range(4):
            for vlmul in LMUL_ENCODINGS:
                try:
                    maximum = vlmax(
                        vsew=vsew, vlmul=vlmul, vlen_bytes=vlen_bits // 8,
                    )
                except ValueError:
                    continue
                for data_eew in EEW_ENCODINGS:
                    try:
                        emul_encoding(vsew=vsew, vlmul=vlmul, eew=data_eew)
                    except ValueError:
                        continue
                    index_eews = EEW_ENCODINGS if operation >= 4 else (0,)
                    for index_eew in index_eews:
                        try:
                            if operation >= 4:
                                emul_encoding(
                                    vsew=vsew, vlmul=vlmul, eew=index_eew,
                                )
                        except ValueError:
                            continue
                        for nf in range(8):
                            bytes_per_element = (nf + 1) * (1 << data_eew)
                            total_bytes = maximum * bytes_per_element
                            uop_count = max(1, (total_bytes + flow_bytes - 1) // flow_bytes)
                            if uop_count > 8:
                                continue
                            yield FeatureCase(
                                operation=operation,
                                vsew=vsew,
                                vlmul=vlmul,
                                data_eew=data_eew,
                                index_eew=index_eew,
                                nf=nf,
                                vlmax=maximum,
                                uop_count=uop_count,
                            )


def fault_positions(case: FeatureCase):
    """All active element positions for precise-fault scenario generation."""
    return tuple(range(case.vlmax))


def representative_public_feature_cases(*, vlen_bits=128, flow_bytes=16):
    """Return a deterministic pairwise-covering set for real-DUT execution.

    The pure generator above is intentionally exhaustive (and is used to audit
    the legal shape space).  Running thousands of independent picker sessions
    would not add useful evidence, so the generated-DUT campaign uses this
    covering set.  It covers every public operation, every SEW/LMUL/EEW/nf and
    uop-count bin, plus operation/parameter pairs.  The selected case itself is
    still compared with the independent RVV oracle at the public request
    boundary.
    """
    remaining = list(legal_public_feature_cases(
        vlen_bits=vlen_bits, flow_bytes=flow_bytes,
    ))

    def tokens(case):
        values = feature_values(case)
        dimensions = PUBLIC_DIMENSIONS
        result = {
            (name, values[name]) for name in dimensions
        }
        result.update(
            (left, right, values[left], values[right])
            for offset, left in enumerate(dimensions)
            for right in dimensions[offset + 1:]
        )
        return frozenset(result)

    uncovered = set().union(*(tokens(case) for case in remaining))
    selected = []
    while uncovered:
        choice = max(
            remaining,
            key=lambda case: (
                len(tokens(case) & uncovered),
                tuple(-value if isinstance(value, int) else value
                      for value in (
                          case.operation, case.vsew, case.vlmul,
                          case.data_eew, case.index_eew, case.nf,
                          case.uop_count,
                      )),
            ),
        )
        selected.append(choice)
        uncovered.difference_update(tokens(choice))
        remaining.remove(choice)
    return tuple(selected)


def feature_values(case: FeatureCase):
    """Return the public functional-coverage value for each dimension."""
    return {
        'operation': OPERATION_NAMES[case.operation],
        'vsew': VSEW_NAMES[case.vsew],
        'vlmul': LMUL_NAMES[case.vlmul],
        'data_eew': EEW_NAMES[case.data_eew],
        'index_eew': EEW_NAMES[case.index_eew] if case.indexed else 'na',
        'nf': str(case.nf),
        'uop_count': str(case.uop_count),
    }


def feature_case_id(case: FeatureCase):
    """Stable identity for one legal shape, suitable for a coverage bin."""
    return (
        f'op{case.operation}_vsew{case.vsew}_vlmul{case.vlmul}'
        f'_data{case.data_eew}_index{case.index_eew if case.indexed else "na"}'
        f'_nf{case.nf}_uop{case.uop_count}'
    )


def pairwise_tokens(case: FeatureCase):
    """Return all marginal and pairwise tokens represented by ``case``."""
    values = feature_values(case)
    # ``index_eew=na`` is a real public feature bin for strided operations, so
    # it participates in the pairwise inventory just like e8/e16/e32/e64 for
    # indexed operations.
    dimensions = PUBLIC_DIMENSIONS
    tokens = {(name, values[name]) for name in dimensions}
    tokens.update(
        (left, right, values[left], values[right])
        for offset, left in enumerate(dimensions)
        for right in dimensions[offset + 1:]
    )
    return frozenset(tokens)


def public_space_metadata(*, vlen_bits=128, flow_bytes=16):
    """Return auditable accounting metadata for the generated shape space."""
    legal = tuple(legal_public_feature_cases(
        vlen_bits=vlen_bits, flow_bytes=flow_bytes,
    ))
    representative = tuple(representative_public_feature_cases(
        vlen_bits=vlen_bits, flow_bytes=flow_bytes,
    ))
    keys = tuple(feature_case_id(case) for case in representative)
    pairwise = set().union(*(pairwise_tokens(case) for case in legal))
    covered = set().union(*(pairwise_tokens(case) for case in representative))
    pairwise_only = {
        token for token in pairwise
        if len(token) == 4
    }
    payload = json.dumps(keys, separators=(',', ':'), sort_keys=False).encode()
    return {
        'generator': 'suites.vector.vagq.vagq.scenario_matrix',
        'version': 2,
        'vlen_bits': vlen_bits,
        'flow_bytes': flow_bytes,
        'legal_case_count': len(legal),
        'representative_case_count': len(representative),
        'representative_unique_case_count': len(set(keys)),
        'pairwise_token_count': len(pairwise),
        'pairwise_covered_by_representative': len(covered),
        'pairwise_cross_count': len(pairwise_only),
        'pairwise_cross_covered_by_representative': len({
            token for token in covered if len(token) == 4
        }),
        'representative_case_sha256': hashlib.sha256(payload).hexdigest(),
        'operations': [OPERATION_NAMES[value] for value in PUBLIC_OPERATIONS],
        'lmul_encodings': list(LMUL_ENCODINGS),
        'eew_encodings': list(EEW_ENCODINGS),
        'nf_values': list(range(8)),
        'uop_count_values': list(range(1, 9)),
        'uop_count_rule': 'ceil(VLMAX * (nf + 1) * bytes(EEW) / flow_bytes) <= 8',
    }
