"""Review event definitions against existing results; never invent a new run.

Path bindings establish traceability, not proof that a reference model is
independent/complete. Empty coverage bindings remain explicit review gaps.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import file_digest
import json
from pathlib import Path

from bpuverify.common.pytest.evidence import worst
from bpuverify.common.pytest.points import domain, make_report, validate_plan

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def identity(path):
    with path.open('rb') as stream:
        return dict(path=str(path.resolve()),sha256=file_digest(stream,'sha256').hexdigest())


def audit(plan, measurement, functional, root, *, planned_additions=()):
    validate_plan(plan)
    planned = {point['id']: point for point in plan['features']}
    measured = {point['id']: point for point in measurement['features']}
    additions = set(planned_additions)
    if (len(measured) != len(measurement['features']) or not measured.keys() <= planned.keys()
            or planned.keys()-measured.keys() != additions):
        raise ValueError('definition review needs the exact measured functional-point universe')
    groups = functional['groups']
    reviewed, verdicts = [], []
    for point in plan['features']:
        old = measured.get(point['id'], dict(id=point['id'],status='NOT_RUN',tests=[]))
        if (point['id'] not in additions and
                (not old.get('tests') or old['status'] != worst({row['status'] for row in old['tests']}))):
            raise ValueError(f"inconsistent measured point verdict: {point['id']}")
        verdicts.append(dict(point,status=old['status'],tests=old['tests']))
        row = dict(id=point['id'],domain=domain(point),component=point['component'],
                   title=point['title'],status=old['status'],tests=old['tests'],
                   definition='documented-needs-event-review',coverage_association='unreviewed',
                   gaps=['event-contract-not-yet-reviewed'])
        if point['id'] in additions:
            row['measurement_scope']='explicit-new-requirement-not-in-retained-run'
        if 'contract' in point:
            row.update(definition='event-contract',gaps=[],contract=point['contract'],evidence=point['evidence'])
            metadata = point.get('metadata', {})
            review = metadata.get('semantic_review', {})
            row.update(semantic_requirements=list(metadata.get('semantic_requirements', [])),
                evidence_limits=review.get('evidence_limits', ''),
                unresolved_specification=review.get('unresolved_specification', ''),
                requirement_verdict_scope='retained-tests-only; subrequirements-not-independently-adjudicated')
            if row['unresolved_specification']:
                row['gaps'].append('unresolved-specification')
            evidence = point['evidence']
            for name in evidence['model']+evidence['checks']:
                path = root/name
                if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
                    raise ValueError(f"missing or out-of-repository semantic binding: {point['id']}: {name}")
            coverage = evidence['coverage']
            row['coverage_values'] = {role:{name:groups.get(name) for name in names}
                                      for role,names in coverage.items()}
            if coverage['reached'] and coverage['checked']:
                row['coverage_association']='paired'
            elif coverage['checked']:
                row['coverage_association']='unpaired-checked-group'
                row['gaps'].append('no-separate-reached-binding')
            else:
                row['coverage_association']='missing'
                row['gaps'].append('no-dedicated-reached-checked-binding')
            for role,names in coverage.items():
                for name in names:
                    if name not in groups:
                        row['gaps'].append('not-measured:'+name)
            if row['coverage_association']=='paired' and any(
                    role_values and all(value==0 for value in role_values.values())
                    for role,role_values in row['coverage_values'].items() if role=='checked'):
                row['gaps'].append('checked-coverage-zero')
        reviewed.append(row)
    report = make_report(verdicts)
    hardware=[row for row in reviewed if row['domain']=='hardware']
    return dict(format='bpu-feature-definition-review',version=1,
        scope='Definition review of retained measurement; NOT a new execution or coverage gain',
        primary_domain='hardware',summaries=report['summaries'],
        definitions=dict(points=len(reviewed),described=sum(bool(p.get('description')) for p in plan['features']),
            hardware=len(hardware),environment=len(reviewed)-len(hardware),
            event_contracts=sum(row['definition']=='event-contract' for row in hardware),
            pending_event_review=sum(row['definition']!='event-contract' for row in hardware),
            coverage_association=dict(Counter(row['coverage_association'] for row in hardware))),
        verdicts_unchanged=True,planned_additions=sorted(additions),points=reviewed)


def markdown(report):
    hardware, environment = (report['summaries'][name] for name in ('hardware','environment'))
    lines=['# 功能点定义审查（不是新测量）','',report['scope'],'',
        f"硬件：{hardware['planned']}点，{hardware['passed']} PASS；环境契约："
        f"{environment['planned']}点，{environment['passed']} PASS。",'',
        '描述存在、事件定义明确、路径关联存在、事件真正到达、比较通过是不同的证据层次。',
        '本文的文件路径关联不等于证明参考模型完备，也不替代pytest判定。',
        '表中保留测量的原判定；新增子义务没有据此获得独立PASS。证据限制和规格未决项必须一同阅读。','',
        '| 功能点 | 原判定 | 事件覆盖关联 | reached / checked（组值，非功能点通过率） |',
        '| --- | --- | --- | --- |']
    for row in report['points']:
        if row['definition']!='event-contract': continue
        values='; '.join(role+': '+', '.join(f'{name}={value}' for name,value in names.items())
                        for role,names in row['coverage_values'].items())
        lines.append(f"| {row['id']} | {row['status']} | {row['coverage_association']} | {values} |")
    lines+=['','以下事件合同区分语义与场景配方；物理坐标和具体周期不是新增功能点。','']
    for row in report['points']:
        if row['definition']!='event-contract': continue
        lines += ['## '+row['id']+'：'+row['title'],'']
        for key,label in (('event','事件'),('owner','所有权'),('effect','效果'),
                          ('observation','观察'),('preservation','不变性'),('scope','范围')):
            lines.append(label+'：'+row['contract'][key])
            lines.append('')
        if row.get('semantic_requirements'):
            lines+=['细化子义务（未按项独立判定，不继承旧PASS）：','']
            for requirement in row['semantic_requirements']:
                lines+=['- '+requirement,'']
        if row.get('evidence_limits'):
            lines+=['现有证据限制：'+row['evidence_limits'],'']
        if row.get('unresolved_specification'):
            lines+=['规格待确认：'+row['unresolved_specification'],'']
        lines+=['关联模型：'+', '.join(row['evidence']['model']),'',
                '关联检查：'+', '.join(row['evidence']['checks']),'',
                '待补证据：'+(', '.join(row['gaps']) or '本次静态关联检查未发现缺项；不表示功能已通过。'),'']
    return '\n'.join(lines)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--measurement',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--planned-addition',action='append',default=[],
                        help='Explicit ID absent from retained run; report it as NOT_RUN, never PASS')
    args=parser.parse_args(argv)
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'results') or output==ROOT/'results':
        parser.error('output must be a new child under results/')
    plan=ROOT/'verification_plan.json'
    features=args.measurement/'feature-points.json'
    functional=args.measurement/'execution/functional-summary.json'
    report=audit(read(plan),read(features),read(functional),ROOT,planned_additions=args.planned_addition)
    report['sources']={name:identity(path) for name,path in
                       (('current_plan',plan),('measured_features',features),('measured_groups',functional))}
    output.mkdir(parents=True,exist_ok=False)
    with (output/'audit.json').open('x') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2)
    with (output/'README.md').open('x') as stream:
        stream.write(markdown(report))
    print(json.dumps(dict(definitions=report['definitions'],summaries=report['summaries']),indent=2))


if __name__=='__main__':
    main()
