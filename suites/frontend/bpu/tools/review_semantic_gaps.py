"""On-demand source-to-event review. No coverage exclusions or PASS credit.

This associates implementation lines with requirements, not missing lines with
invented root causes. Control anchors may implement more than one event. New
source shapes stay unresolved instead of silently inheriting a module label.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re

from bpuverify.common.coverage.local_guards import Source, claim, match_native, native_points
from bpuverify.sc.coverage.guard_audit import source_claims as sc_claims
from bpuverify.tage.coverage.coverage_audit import source_claims as tage_claims
from bpuverify.bpu.coverage.history_gaps import assignment, local_claims, constrained_claims
from bpuverify.bpu.coverage.main_gaps import associate
from tools.coverage_delta import lcov_rows

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT/'docs/functional-events.json'
NAMES = dict(sc='Sc', tage='Tage', bpu='Bpu', utage='Utage', mbtb='Mbtb', ras='Ras')


def shadow_role(text, previous):
    """Only the five source forms actually reviewed; not every shadow path."""
    if text == 'if (io_train_t1_alloc_valid)':
        return 'allocation-choice', ('useful.allocate','useful.change','useful.hold')
    if re.fullmatch(r'usefulEntries_\d+_\d+_value <= 2\x27h[12];', text):
        return 'allocation-initialize', ('useful.allocate',)
    if re.fullmatch(r'else if \(_newUseful_T_\d+\)', text):
        return 'saturation-choice', ('useful.hold','useful.change')
    if (re.fullmatch(r'usefulEntries_\d+_\d+_value <= _GEN_\d+;', text)
            and re.fullmatch(r'else if \(_newUseful_T_\d+\)', previous)):
        return 'saturation-preserve', ('useful.hold',)
    if re.fullmatch(r'usefulEntries_\d+_\d+_value <= _newUseful_T_\d+;', text):
        return 'counter-change', ('useful.change',)
    return 'UNRESOLVED', ()


def validate_catalog(catalog, plan):
    ids = {p['id'] for p in plan['features']}
    for event in catalog['events'].values():
        for field in ('title','event','effect','observation','source'):
            if not isinstance(event[field], str) or not event[field].strip():
                raise ValueError(f'empty semantic definition: {field}')
        if any(identity not in ids for names in event['features'].values() for identity in names):
            raise ValueError('semantic catalog references an unknown functional point')
        path, number = event['source'].rsplit(':',1)
        if not 0 < int(number) <= len((ROOT/path).read_text().splitlines()):
            raise ValueError('semantic source reference is outside source file')


def transfer(claims, original, compiled):
    a, b = Source(original), Source(compiled)
    # A generated suffix is not evidence of equivalence. Only the module
    # declaration may differ; every other source body line must match.
    if a.lines[:45]+a.lines[46:] != b.lines[:45]+b.lines[46:]:
        raise ValueError(f'cannot transfer local guard proof to {compiled}')
    return [dict(c,file=compiled) for c in claims]


def held_repair_witnesses(*, relax_parent=False):
    return [dict(valid=v,repair=r,call=c) for v,r,c in product((False,True),repeat=3)
            if v and r and (relax_parent or not v) and c]


def micro_ras_parent_claims():
    parent, child = Source('rtl/bpu/Bpu.sv'), Source('rtl/bpu/MicroRas.sv')
    expression=assignment(parent,'s2_override')
    assert expression.startswith('s2_valid&(') and expression.endswith(')')
    # The whole remaining expression must be the other operand of AND;
    # accepting just a prefix would miss a newly added top-level OR bypass.
    depth=0
    for index,token in enumerate(expression[len('s2_valid&'):]):
        depth += (token=='(')-(token==')')
        assert depth>0 or index==len(expression)-len('s2_valid&')-1
    assert depth==0
    at = parent.unique('MicroRas uras (')
    instance = ''.join(parent.lines[at-1:]).split(');',1)[0]
    compact = re.sub(r'\s+','',instance)
    assert compact.count('.io_stageCtrl_s2_fire(s2_valid),') == 1
    assert compact.count('.io_s2OverrideData_valid(s2_override),') == 1
    first = child.unique('if (io_s2OverrideData_valid & ~io_stageCtrl_s2_fire & s2_realPush)')
    child.expect(first+1,'s2_retAddr_addr <= _s2_realPushAddr_T_3[50:1];')
    assert not held_repair_witnesses() and held_repair_witnesses(relax_parent=True)
    # The frozen native schema lowers this source IF as an ELSIF. The parent
    # implication excludes it regardless of additional priority predicates;
    # match_native still requires this exact arm for ALL overlapping producers.
    return [claim('rtl/bpu/MicroRas.sv',first,first+1,first,'elsif',
                  'integrated-s2-repair-implies-stage-advance')], parent


def review(baseline):
    baseline = Path(baseline).resolve()
    read = lambda name: json.loads((baseline/name).read_text())
    report, epoch, manifest = read('rtl-line-coverage.json'), read('source-epoch.json'), read('execution/manifest.json')
    if manifest['state']!='committed' or not manifest['coverage_complete']:
        raise ValueError('event review requires a complete committed measurement, including its failures')
    if manifest['pytest_exitstatus'] != report['pytest_exitstatus']:
        raise ValueError('measurement exit statuses disagree')
    catalog = json.loads(CATALOG.read_text())
    plan = json.loads((ROOT/'verification_plan.json').read_text())
    validate_catalog(catalog,plan)
    native = {}
    for dut, name in NAMES.items():
        artifacts = [a for a in manifest['artifacts'] if a['kind']=='native' and a['build']['name']==f'DUT{name}Dut']
        if len(artifacts)!=1:
            raise ValueError(f'expected one final native schema for {dut}')
        item = artifacts[0]; path = Path(item['path']).resolve()
        if not path.is_relative_to(baseline) or sha256(path.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('native schema changed or escaped measurement')
        native[dut] = native_points(path)

    sc, _ = sc_claims(); tage, _ = tage_claims(report)
    proofs = {'sc': sc, 'tage': tage, 'bpu': transfer(tage,'rtl/tage/WriteBuffer.sv','rtl/bpu/WriteBuffer_8.sv')}
    for source, dest in (('rtl/sc/WriteBuffer.sv','rtl/bpu/WriteBuffer_30.sv'),
                         ('rtl/sc/WriteBuffer_8.sv','rtl/bpu/WriteBuffer_38.sv')):
        proofs['bpu'] += transfer([c for c in sc if c['file']==source],source,dest)
    phr = Source('rtl/bpu/Phr.sv')
    raw = {(r['file'],r['line']) for r in report['dut']['bpu']['uncovered_rtl_source_lines']}
    local, (conditional, cursor_contract) = local_claims(phr), constrained_claims(phr,raw)
    proofs['bpu'] += local+conditional
    micro, parent = micro_ras_parent_claims()
    proofs['bpu'] += micro
    if epoch.get(str(ROOT/parent.path))!=parent.sha256:
        raise ValueError('stale BPU parent connection proof')
    proven = {dut:match_native(claims,report,dut,native[dut]) for dut,claims in proofs.items()}
    guards = {(dut,c['file'],n): c['kind'] for dut,claims in proofs.items()
              for c in claims for n in range(c['first'],c['last']+1)}
    main = associate(report['dut']['bpu']['uncovered_rtl_source_lines'],native['bpu'],
        (ROOT/'rtl/bpu/WriteBuffer_4.sv').read_text(), source_path=str(ROOT/'rtl/bpu/WriteBuffer_4.sv'))
    sources, groups = {}, defaultdict(list)
    for dut, measured in report['dut'].items():
        rows = measured['uncovered_rtl_source_lines']
        lcov = lcov_rows(measured['lcov_file'])
        zeros = {(str(Path(f).resolve()),n) for (f,n),value in lcov.items() if value==0}
        if measured['source_lines'] != dict(total=len(lcov), hit=sum(v>0 for v in lcov.values())):
            raise ValueError('native denominator disagrees with LCOV')
        keys = {(str((ROOT/r['file']).resolve()),r['line']) for r in rows}
        if len(keys)!=len(rows) or keys!=zeros:
            raise ValueError('uncovered rows are not the exact native zero DA set')
        for row in rows:
            file, number, module = row['file'],row['line'],row['module']
            if file not in sources:
                path=ROOT/file; digest=sha256(path.read_bytes()).hexdigest()
                if epoch.get(str(path))!=digest: raise ValueError(f'stale measured RTL: {file}')
                sources[file] = dict(sha256=digest, lines=path.read_text().splitlines())
            lines=sources[file]['lines']
            if lines[number-1].strip()!=row['verilog'].strip(): raise ValueError('native source text changed')
            text=lines[number-1].split('//',1)[0].strip()
            previous=lines[number-2].split('//',1)[0].strip() if number>1 else ''
            role, events, cause = 'UNRESOLVED', (), 'requires-source-review'
            proof = guards.get((dut,file,number))
            if module in ('BypassShadowBuffer','BypassShadowBuffer_1'):
                role,events=shadow_role(text,previous)
                cause='defined-event-not-closed; qualification/failure/physical-attribution-still-open'
            elif module=='AheadBtb' and row.get('counter_gap'):
                role=row['counter_gap']['role']
                events=(('ahead.replace',) if role=='reset_weak_positive' else
                        ('ahead.reward',) if role=='increment_assignment' else ('ahead.penalize',))
                cause='defined-event-with-unvisited-physical-copies; no-equivalence-proof'
            elif module in ('AheadBtbReplacer','ReplacerState','ReplacerState_4'):
                role='policy-comparison-mirror' if module=='AheadBtbReplacer' else 'replacement-recency'
                events=('replacement.touch',)
                cause='auxiliary-policy-comparison-copy' if module=='AheadBtbReplacer' else 'physical-and-semantic-scenario-attribution-open'
                if dut=='bpu' and module=='ReplacerState_4':
                    events=('main.replacement-forward',)
                    cause='new-integrated-main-replacement-requirement; actual-test-evidence-required'
                elif dut=='mbtb':
                    events=('replacement.touch','main.replacement-forward')
            elif module.startswith('WriteBuffer'):
                events=('main.rewrite',) if module=='WriteBuffer_4' else ('pending.rewrite',)
                role='buffer-update'
                if module=='WriteBuffer_4':
                    role=main['copies'][main['missing_line_to_copy'][str(number)]]['family']
                cause='integrated-owner/input-effect-consumer-closure-open'
            elif module=='Phr': role,events,cause='history-replay',('path.recover',),'requires-source-review'
            elif module=='CommonHR': role,events,cause='history-recovery-priority',('common.recover',),'local-priority-source-review; no-new-functional-event-inferred'
            elif module=='RasStack': role,events,cause='committed-call-lifetime',('ras.retire',),'guard-or-physical-copy-attribution; not-new-per-slot-features'
            elif module=='MicroRas': role,events,cause='held-call-repair',('micro-ras.repair',),'missing-integrated-event-definition; legal-stall-witness-not-yet-established'
            if proof:
                cause=('conditional-owned-checkpoint-residue' if proof=='owned-checkpoint-cursor-residue' else
                       'bounded-parent-connection-constraint' if proof=='integrated-s2-repair-implies-stage-advance' else
                       'bounded-local-guard-contradiction')
            groups[dut,file,module,role,events,cause,proof].append(number)
    result=[]
    for (dut,file,module,role,events,cause,proof), numbers in sorted(groups.items(),key=lambda x:str(x[0])):
        features=sorted({p for event in events for p in catalog['events'][event]['features'].get(dut,[])})
        result.append(dict(dut=dut,file=file,module=module,implementation_role=role,events=list(events),
            related_features=features,cause_status=cause,guard_kind=proof,lines=sorted(numbers),count=len(numbers)))
    return dict(format='bpu-source-semantic-event-review',version=1,baseline=str(baseline),
        scope='exact native zero DA -> implementation role -> semantic requirements; NOT new execution, causal proof or PASS',
        measurement_sha256=sha256((baseline/'rtl-line-coverage.json').read_bytes()).hexdigest(),
        catalog_sha256=sha256(CATALOG.read_bytes()).hexdigest(),plan_sha256=sha256((ROOT/'verification_plan.json').read_bytes()).hexdigest(),
        source_sha256={name:entry['sha256'] for name,entry in sources.items()},
        parent_connection_sha256=parent.sha256,
        native_pytest_exitstatus=report['pytest_exitstatus'],native_denominator_unchanged=True,functional_pass_credit=False,
        raw_missing=sum(g['count'] for g in result),unresolved=sum(g['count'] for g in result if not g['events']),
        cursor_contract=cursor_contract,guard_reviews=proven,main_source_native_association=main,groups=result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('preserve existing reviews; choose a fresh output file')
    result=review(args.baseline)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream: json.dump(result,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps(dict(raw_missing=result['raw_missing'],unresolved=result['unresolved'],
        by_dut=dict(Counter({d:sum(g['count'] for g in result['groups'] if g['dut']==d) for d in NAMES})),
        by_cause=dict(Counter({c:sum(g['count'] for g in result['groups'] if g['cause_status']==c)
                              for c in {g['cause_status'] for g in result['groups']}}))),ensure_ascii=False))


if __name__=='__main__': main()
