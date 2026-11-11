"""Collected feature-marker verdicts; these are not functional coverage bins.

Version 2 reports use hardware as the primary summary and retain explicit
hardware/environment/all partitions. Legacy reports remain immutable/readable.
The legacy ``planned`` and ``completion_rate`` fields describe only the supplied
marker catalogue, never completeness of a verification specification.
"""
from collections import Counter

import pytest

STATES = ('ERROR', 'FAIL', 'XPASS', 'INCOMPLETE', 'UNCERTAIN', 'PASS', 'XFAIL', 'SKIP', 'NOT_RUN')
DOMAINS = ('hardware', 'environment')
SCOPE = 'collected-test-markers'


def domain(point):
    inferred = 'environment' if point['id'].startswith('ENV-') else 'hardware'
    value = point.get('metadata', {}).get('domain', inferred)
    if value not in DOMAINS or value != inferred:
        raise ValueError(f"invalid verification domain for {point['id']}: {value}")
    return value


def marker_ids(item):
    ids = set()
    for marker in item.iter_markers('feature'):
        if (len(marker.args) != 1 or not isinstance(marker.args[0], str)
                or not marker.args[0].strip()):
            raise pytest.UsageError(f'{item.nodeid}: feature marker needs one non-empty ID')
        ids.add(marker.args[0])
    return sorted(ids)


def merge_feature_nodes(mapping, incoming):
    """Accept worker attachments without an external allowlist; detect drift."""
    if not isinstance(incoming, dict):
        raise ValueError('invalid feature mapping')
    for nodeid, ids in incoming.items():
        if (not isinstance(nodeid, str) or not nodeid or not isinstance(ids, list)
                or any(not isinstance(value, str) or not value.strip() for value in ids)
                or ids != sorted(set(ids))):
            raise ValueError(f'invalid feature mapping: {nodeid}')
        if nodeid in mapping and mapping[nodeid] != ids:
            raise ValueError(f'feature mapping changed: {nodeid}')
    mapping.update(incoming)


def feature_catalogue(mapping):
    """Derive report rows after collection/report attachments have arrived."""
    return [dict(id=identity, title=identity, component=identity.rsplit('-', 1)[0])
            for identity in sorted({identity for ids in mapping.values() for identity in ids})]


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
    scope = extra.pop('scope', SCOPE)
    if scope != SCOPE:
        raise ValueError('feature report scope must be collected-test-markers')
    points = list(points)
    ids = [point['id'] for point in points]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate verification-point report identity')
    partitions = {name: summarize([point for point in points if domain(point)==name])
                  for name in DOMAINS}
    partitions['all'] = summarize(points)
    return dict(format='bpu-feature-report', version=2, scope=scope, summary_domain='hardware',
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
    if 'scope' in report and report['scope'] != SCOPE:
        raise ValueError('feature report scope must be collected-test-markers')
    expected = make_report(report['features'])
    if 'scope' not in report:
        # Historical v2 summaries predate these outcomes. Keep their zero-key
        # vocabulary readable without rewriting the stored evidence.
        for summary in expected['summaries'].values():
            for state in ('INCOMPLETE', 'UNCERTAIN'):
                if summary['status_counts'][state] == 0:
                    summary['status_counts'].pop(state)
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
