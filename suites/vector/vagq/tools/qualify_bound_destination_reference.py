"""Qualify the repaired architectural model, including no-op and identity.

Bindings and allowed results come from the frozen independent register oracle,
not candidate.mop_info, allocated_uops, RTL or native observations.
"""
from collections import Counter
from dataclasses import asdict, replace
from fractions import Fraction
import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.qualify_maskgen_semantics import configurations, profiles
from tools.run_vagq_exhaustive import atomic_json, digest
from suites.vector.vagq.maskgen.architectural import BoundDestination, DestinationBinding, DestinationInstruction
from suites.vector.vagq.maskgen.reference import MaskRequest, evaluate
from suites.vector.vagq.qualification.rvv_destination import Instruction as Oracle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    journal_path = output / 'configurations.jsonl'
    if journal_path.exists():
        raise RuntimeError('preserve previous qualification; use a fresh output')
    total = Counter()
    transcript = hashlib.sha256()
    mutations = Counter()
    rng = random.Random(0x424F554E44)
    with journal_path.open('x') as journal:
        for deew, ieew, encoding, emul, fields, maximum in configurations():
            local = Counter()
            masks = (0, (1 << maximum) - 1,
                     sum(1 << bit for bit in range(maximum) if bit % 2), rng.getrandbits(maximum))
            for vl, start in profiles(maximum, rng):
                for mask in masks:
                    oracle = Oracle(1 << deew, emul, fields, vl, start, mask)
                    for vma, vta in ((0, 0), (0, 1), (1, 0), (1, 1)):
                        instruction = DestinationInstruction(1 << deew, emul, fields, vl, start, mask, vma, vta)
                        for tag, register in enumerate(oracle.registers()):
                            bound = BoundDestination(instruction, DestinationBinding(register.field, register.number, tag))
                            request = MaskRequest(oracle.expanded_mask(register), deew, ieew,
                                encoding, vl, start, vma, vta, tag, fields - 1)
                            # Unlike the prior qualification, register identity
                            # is an INPUT, never read back from the candidate.
                            result = evaluate(request, destination=bound)
                            errors = oracle.check_merge_controls(register, merge_mask=result.merge_write_mask,
                                agnostic_mask=result.agnostic_byte_mask, vma=vma, vta=vta)
                            assert result.element_indices == register.elements
                            assert result.instruction_executes == (start < vl)
                            assert result.destination_commit_allowed == (start < vl)
                            expected_memory = tuple(element for element in register.elements
                                if start <= element < vl and (mask >> element) & 1)
                            assert result.memory_elements == expected_memory
                            assert not errors, (request, bound, result, errors)
                            kind = 'noop' if oracle.no_op else 'running'
                            local[kind + '_checks'] += 1
                            local[kind + '_violations'] += bool(errors)
                            transcript.update(json.dumps(dict(input=asdict(request), field=register.field,
                                register=register.number, result=asdict(result)), sort_keys=True).encode())
                            # Targeted errors are rejected by the same independent
                            # oracle; no expected value is taken from the RTL.
                            if start < vl:
                                bad = oracle.check_merge_controls(register, merge_mask=0xFFFF,
                                    agnostic_mask=0, vma=vma, vta=vta)
                                mutations['active_clobber_checks'] += 1
                                mutations['active_clobber_rejected'] += bool(bad)
                            if oracle.no_op and any(element >= vl for element in register.elements):
                                bad = oracle.check_merge_controls(register, merge_mask=0xFFFF,
                                    agnostic_mask=0xFFFF, vma=1, vta=1)
                                mutations['noop_ones_checks'] += 1
                                mutations['noop_ones_rejected'] += bool(bad)
            journal.write(json.dumps(dict(data_eew=deew, index_eew=ieew, emul=str(emul),
                fields=fields, counts=dict(local))) + '\n')
            journal.flush()
            total.update(local)
            total['configurations'] += 1
    assert total['configurations'] == 401 and total['noop_checks'] > 0
    assert total['running_violations'] == total['noop_violations'] == 0
    assert mutations['active_clobber_rejected'] > 0
    assert mutations['noop_ones_checks'] == mutations['noop_ones_rejected'] > 0
    names = ('maskgen/architectural.py', 'maskgen/reference.py',
        'qualification/rvv_destination.py', 'tools/qualify_maskgen_semantics.py',
        'tools/qualify_bound_destination_reference.py', 'tests/maskgen/test_architectural_reference.py')
    for name in names:
        target = output / 'sources' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    atomic_json(output / 'source-hashes.json', {name: digest(ROOT / name) for name in names})
    summary = dict(counts=dict(total), mutations=dict(mutations),
        no_op_requires_unverified_upstream_gate=False,
        architectural_register_identity='Explicit input from independent oracle enumeration; no candidate-window lookup',
        expected_values='Frozen independent RVV register oracle; not native/RTL agreement',
        architecture_reference_status='PASS_FOR_DECLARED_BOUND_DESTINATION_DOMAIN',
        actual_rtl_producer_mapping='NOT_CLAIMED',
        full_lsu_vrf_memory_effect='NOT_CLAIMED',
        new_native_coverage_credit=0, evaluated_transcript_sha256=transcript.hexdigest(),
        journal_sha256=digest(journal_path))
    atomic_json(output / 'summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
