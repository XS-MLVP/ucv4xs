"""Verification-point verdicts; these are not functional coverage bins.

Version 2 reports use hardware as the primary summary and retain explicit
hardware/environment/all partitions. Legacy reports remain immutable/readable.
"""
from collections import Counter

STATES = ('ERROR', 'FAIL', 'XPASS', 'PASS', 'XFAIL', 'SKIP', 'NOT_RUN')
DOMAINS = ('hardware', 'environment')


def domain(point):
    inferred = 'environment' if point['id'].startswith('ENV-') else 'hardware'
    value = point.get('metadata', {}).get('domain', inferred)
    if value not in DOMAINS or value != inferred:
        raise ValueError(f"invalid verification domain for {point['id']}: {value}")
    return value


def validate_plan(plan):
    if plan.get('version', 1) not in (1, 2):
        raise ValueError('unsupported verification plan version')
    points = plan['features']
    ids = [point['id'] for point in points]
    if len(ids) != len(set(ids)):
        raise ValueError('verification plan contains duplicate feature IDs')
    for point in points:
        domain(point)
        if plan.get('version', 1) < 2:
            continue
        if not point.get('description', '').strip():
            raise ValueError(f"{point['id']}: missing verification-point description")
        if point.get('metadata', {}).get('domain') not in DOMAINS:
            raise ValueError(f"{point['id']}: missing explicit verification domain")
        requirements = point['metadata'].get('semantic_requirements', [])
        if (not isinstance(requirements, list)
                or any(not isinstance(value, str) or not value.strip() for value in requirements)
                or len(requirements) != len(set(requirements))):
            raise ValueError(f"{point['id']}: invalid semantic requirements")
        if 'contract' in point:
            fields = ('event','owner','effect','observation','preservation','scope')
            if (set(point['contract']) != set(fields)
                    or any(not isinstance(point['contract'][key], str)
                           or not point['contract'][key].strip() for key in fields)):
                raise ValueError(f"{point['id']}: incomplete semantic event contract")
            evidence = point.get('evidence', {})
            for role in ('model', 'checks'):
                paths = evidence.get(role)
                if (not isinstance(paths, list) or not paths
                        or any(not isinstance(path, str) or not path for path in paths)):
                    raise ValueError(f"{point['id']}: missing semantic {role} binding")
            coverage = evidence.get('coverage', {})
            if set(coverage) != {'reached', 'checked'}:
                raise ValueError(f"{point['id']}: separate reached/checked bindings required")
            for names in coverage.values():
                if (not isinstance(names, list)
                        or any(not isinstance(name, str) or not name for name in names)
                        or len(names) != len(set(names))):
                    raise ValueError(f"{point['id']}: invalid semantic coverage binding")
            if coverage['reached'] and coverage['checked']:
                if (any(not name.endswith('.reached') for name in coverage['reached'])
                        or any(not name.endswith('.checked') for name in coverage['checked'])):
                    raise ValueError(f"{point['id']}: paired coverage must name explicit reached/checked groups")


def summarize(points):
    counts = Counter(point['status'] for point in points)
    if not set(counts) <= set(STATES):
        raise ValueError('unknown verification-point verdict')
    planned = len(points)
    executed = planned - counts['NOT_RUN'] - counts['SKIP']
    passed = counts['PASS']
    return dict(planned=planned, executed=executed, passed=passed,
        status_counts={state: counts[state] for state in STATES},
        execution_rate=100*executed/planned if planned else 100.,
        pass_rate=100*passed/executed if executed else 0.,
        completion_rate=100*passed/planned if planned else 100.)


def make_report(points, **extra):
    points = list(points)
    ids = [point['id'] for point in points]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate verification-point report identity')
    partitions = {name: summarize([point for point in points if domain(point)==name])
                  for name in DOMAINS}
    partitions['all'] = summarize(points)
    return dict(format='bpu-feature-report', version=2, summary_domain='hardware',
                features=points, summary=partitions['hardware'], summaries=partitions, **extra)


def summary_for(report, name='hardware'):
    if report.get('version', 1) == 2:
        return report['summaries'][name]
    if name == 'all':
        return report['summary']
    return summarize([point for point in report['features'] if domain(point)==name])


def validate_report(report):
    """Check every partition, including failing environment points and rates."""
    if report.get('version', 1) == 1:
        return  # The historical publication validator checks v1 totals.
    if report['version'] != 2:
        raise ValueError('unsupported verification-point report version')
    expected = make_report(report['features'])
    if report.get('summary_domain') != 'hardware':
        raise ValueError('primary verification-point summary must be hardware')
    if set(report.get('summaries', {})) != {*DOMAINS, 'all'}:
        raise ValueError('incomplete verification-point partitions')
    summaries = dict(report['summaries'], primary=report.get('summary', {}))
    for name, summary in summaries.items():
        for key in ('planned', 'executed', 'passed'):
            if type(summary.get(key)) is not int:
                raise ValueError('verification-point counts must be integers')
        counts = summary.get('status_counts', {})
        if any(type(value) is not int for value in counts.values()):
            raise ValueError('verification-point verdict counts must be integers')
        for key in ('execution_rate', 'pass_rate', 'completion_rate'):
            if type(summary.get(key)) not in (int, float):
                raise ValueError('verification-point rates must be numeric')
        target = expected['summary'] if name=='primary' else expected['summaries'][name]
        if summary != target:
            raise ValueError(f'verification-point summary differs from verdicts: {name}')
