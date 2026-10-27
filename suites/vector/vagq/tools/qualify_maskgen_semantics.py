"""Architectural qualification independent of RTL/native agreement.

The candidate is inspected as a black-box model. The oracle receives only
architectural register identities and values; it never consumes candidate
mask/window equations. Uop-to-register identity is explicitly NOT certified.
"""
from collections import Counter
from dataclasses import asdict, replace
from fractions import Fraction
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.run_vagq_exhaustive import atomic_json, digest
from vagqverify.maskgen import reference as candidate
from vagqverify.qualification.rvv_destination import Instruction


EMUL = ((5, Fraction(1, 8)), (6, Fraction(1, 4)), (7, Fraction(1, 2)),
        (0, Fraction(1)), (1, Fraction(2)), (2, Fraction(4)), (3, Fraction(8)))


def configurations():
    # Domain follows RVV EMUL/NFIELDS and index/data operand-ratio rules,
    # NOT candidate.legal or generated tables.
    for deew in range(4):
        for encoding, emul in EMUL:
            maximum = 16 * emul / (1 << deew)
            if maximum < 1 or maximum.denominator != 1:
                continue
            for fields in range(2, 9):
                if emul * fields > 8:
                    continue
                for ieew in range(4):
                    index_emul = emul * (1 << ieew) / (1 << deew)
                    if Fraction(1, 8) <= index_emul <= 8:
                        yield deew, ieew, encoding, emul, fields, int(maximum)


def geometry(module, configuration, *, reset_windows=False):
    deew, ieew, encoding, emul, fields, maximum = configuration
    architecture = Instruction(1 << deew, emul, fields, maximum, 0, (1 << maximum) - 1)
    registers = architecture.registers()
    expected = Counter(register.elements[0] // len(register.elements) for register in registers)
    request = module.MaskRequest(0xFFFF, deew, ieew, encoding, maximum, 0, 0, 0, 0, fields - 1)
    if not request.legal:
        return dict(expected=dict(expected), actual={}, correct=False, reason='candidate rejects independent domain'), []
    bindings, actual = [], Counter()
    for index in range(len(module.allocated_uops(request))):
        info = module.mop_info(replace(request, uop_idx=index))
        if info.skip_merge:
            continue
        window = 0 if reset_windows else info.destination_window
        occurrence = actual[window]
        actual[window] += 1
        # Matching claimed register windows to architectural registers checks
        # policy consistency and counts, NOT actual decoder/rename identity.
        register = next((reg for reg in registers
            if reg.field == occurrence and reg.elements[0] // len(reg.elements) == window), None)
        if register is not None:
            bindings.append((index, register))
    return dict(expected=dict(expected), actual=dict(actual), correct=expected == actual), bindings


def controls(module, request, mutation=None):
    if mutation == 'invert_mask':
        request = replace(request, v0_mask=request.v0_mask ^ 0xFFFF)
    evaluator = getattr(module, 'evaluate_protocol', module.evaluate)
    result = dict(evaluator(request))
    if mutation == 'clobber_active_with_old':
        result.update(mergeWriteMask=0xFFFF, elemAgnosticMask=0)
    elif mutation == 'write_prestart_ones':
        result['mergeWriteMask'] |= 1
        result['elemAgnosticMask'] |= 1
    elif mutation == 'drop_preservation':
        result.update(mergeWriteMask=0, elemAgnosticMask=0)
    elif mutation == 'retain_old_when_agnostic':
        # This differs from DUT's selected agnostic policy but is RVV-legal.
        result['elemAgnosticMask'] = 0
    return result


def profiles(maximum, rng):
    values = set()
    for vl in (0, 1, maximum // 2, max(0, maximum - 1), maximum):
        for start in (0, min(1, maximum - 1), min(vl, maximum - 1), max(0, min(vl - 1, maximum - 1))):
            values.add((vl, start))
    for _ in range(8):
        values.add((rng.randrange(maximum + 1), rng.randrange(maximum)))
    return sorted(values)


def qualify(module, configs, *, mutation=None, include_random=True):
    totals = Counter()
    details = []
    rng = random.Random(0x52565610)
    for configuration in configs:
        deew, ieew, encoding, emul, fields, maximum = configuration
        dimension, bindings = geometry(module, configuration, reset_windows=mutation == 'reset_all_windows')
        totals['configurations'] += 1
        totals['geometry_pass'] += dimension['correct']
        totals['geometry_fail'] += not dimension['correct']
        local = Counter()
        examples = []
        transcript = hashlib.sha256()
        masks = (0, (1 << maximum) - 1,
                 sum(1 << bit for bit in range(maximum) if bit % 2),
                 rng.getrandbits(maximum))
        pairs = profiles(maximum, rng) if include_random else [(maximum, 0), (max(1, maximum - 1), min(1, maximum - 1))]
        for vl, start in pairs:
            for mask in masks:
                instruction = Instruction(1 << deew, emul, fields, vl, start, mask)
                for vma, vta in ((0, 0), (0, 1), (1, 0), (1, 1)):
                    for index, register in bindings:
                        request = module.MaskRequest(instruction.expanded_mask(register),
                            deew, ieew, encoding, vl, start, vma, vta, index, fields - 1)
                        result = controls(module, request, mutation)
                        errors = instruction.check_merge_controls(register,
                            merge_mask=result['mergeWriteMask'], agnostic_mask=result['elemAgnosticMask'],
                            vma=vma, vta=vta)
                        kind = 'noop_without_producer_gate' if instruction.no_op else 'running_instruction'
                        local[kind + '_checks'] += 1
                        local[kind + '_violations'] += bool(errors)
                        transcript.update(json.dumps(dict(request=asdict(request),
                            register=asdict(register), controls=result, errors=errors), sort_keys=True).encode())
                        if errors and len(examples) < 3:
                            examples.append(dict(scope=kind, request=asdict(request),
                                architectural_register=asdict(register), errors=errors,
                                proposed_controls=result))
        totals.update(local)
        details.append(dict(configuration=dict(data_eew=deew, index_eew=ieew,
            emul_encoding=encoding, emul=str(emul), fields=fields, vlmax=maximum),
            geometry=dimension, counts=dict(local), examples=examples,
            evaluated_transcript_sha256=transcript.hexdigest()))
    return dict(totals), details


def load_old(path):
    name = 'frozen_pre_repair_maskgen_candidate'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    counts, details = qualify(candidate, tuple(configurations()))
    atomic_json(out / 'architectural-checks.json', details)
    old_path = out.parent / 'before/vagqverify/maskgen/reference.py'
    old = load_old(old_path)
    # Fixed architectural witnesses; no DUT samples or generated tables.
    witnesses = ((2, 2, 0, Fraction(1), 3, 4),
                 (2, 2, 1, Fraction(2), 2, 8),
                 (1, 1, 6, Fraction(1, 4), 5, 2))
    mutations = []
    old_counts, _ = qualify(old, witnesses, include_random=False)
    mutations.append(dict(name='actual_frozen_old_reference', result='REJECTED'
        if old_counts['geometry_fail'] or old_counts['running_instruction_violations'] else 'SURVIVED',
        counts=old_counts, source_sha256=digest(old_path)))
    for mutation in ('reset_all_windows', 'clobber_active_with_old', 'invert_mask',
                     'write_prestart_ones', 'drop_preservation', 'retain_old_when_agnostic'):
        result, _ = qualify(candidate, witnesses, mutation=mutation, include_random=False)
        rejected = result['geometry_fail'] or result['running_instruction_violations']
        expected_legal = mutation == 'retain_old_when_agnostic'
        mutations.append(dict(name=mutation, result='REJECTED' if rejected else 'ACCEPTED',
            expected='ACCEPTED' if expected_legal else 'REJECTED', counts=result))
    assert all(item['result'] == item.get('expected', 'REJECTED') for item in mutations)
    atomic_json(out / 'mutation-results.json', mutations)
    for name in ('vagqverify/qualification/rvv_destination.py', 'tests/maskgen/test_architectural_qualification.py',
                 'tools/qualify_maskgen_semantics.py', 'vagqverify/maskgen/reference.py'):
        target = out / 'sources' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    source_names = [str(path.relative_to(out / 'sources')) for path in (out / 'sources').rglob('*.py')]
    atomic_json(out / 'source-hashes.json', {name: digest(out / 'sources' / name) for name in source_names})
    summary = dict(qualification_basis='Official RVV v1.0 architectural destination values, not DUT agreement',
        oracle_imports=['dataclasses', 'fractions'], seed='0x52565610', counts=counts,
        running_merge_policy_qualified=counts['geometry_fail'] == counts['running_instruction_violations'] == 0,
        frozen_old_reference_rejected=mutations[0]['result'] == 'REJECTED',
        erroneous_mutants_rejected=6,
        legal_different_agnostic_policy_accepted=mutations[-1]['result'] == 'ACCEPTED',
        no_op_without_gate_qualified=counts['noop_without_producer_gate_violations'] == 0,
        whole_reference_correctness='NOT_CERTIFIED',
        independently_unproven=['Concrete decoder/rename uop-to-architectural-register identity',
            'Producer no-op suppression for every admitted path',
            'MOP allocation/index bank payload/LSU/VRF final effects'],
        interpretation='The element-window repair has independent architectural evidence; this is not certification of the whole implementation-specific model.',
        checks_sha256=digest(out / 'architectural-checks.json'), mutations_sha256=digest(out / 'mutation-results.json'))
    atomic_json(out / 'summary.json', summary)
    print(json.dumps(summary, indent=2))
    assert summary['running_merge_policy_qualified']


if __name__ == '__main__':
    main()
