"""Persistent design identities and reviewed, offline baseline reconciliation. MPL-2.0.

The catalog is navigation/identity metadata, not a verification plan. Observations
never update tracking fields, DUT recipes, contracts, or hardware verdicts.
"""
from copy import deepcopy
import re

from .common import UcvError, contained, digest, file_hash, lock, read, write

IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
STATES = {'active', 'inlined', 'split', 'merged', 'replaced', 'retired'}
AVAILABILITY = {'present', 'absent', 'unobserved', 'documented'}
BINDING_FIELDS = {'availability', 'source', 'rtl_tops', 'instances',
                  'actual_parent_edges', 'placement', 'grouping'}


def require(condition, message):
    if not condition:
        raise UcvError('Module catalog: ' + message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def identifier(value):
    return isinstance(value, str) and bool(IDENTIFIER.fullmatch(value))


def strings(value):
    return isinstance(value, list) and all(text(v) for v in value)


def evidence_table(value):
    require(isinstance(value, dict), 'evidence must be an object')
    for key, row in value.items():
        require(identifier(key) and isinstance(row, dict), 'invalid evidence entry')
        require(text(row.get('reference')) and isinstance(row.get('sha256'), str)
                and SHA256.fullmatch(row['sha256']), f'incomplete evidence: {key}')


def evidence_refs(value, evidence):
    require(strings(value) and value and set(value) <= evidence.keys(),
            'evidence references must identify retained hashes')


def binding(value):
    require(isinstance(value, dict), 'observation must be an object')
    require(isinstance(value.get('availability'), str) and value['availability'] in AVAILABILITY,
            'invalid availability')
    require(strings(value.get('rtl_tops')) and len(set(value['rtl_tops'])) == len(value['rtl_tops']),
            'rtl_tops must be unique strings')
    source = value.get('source')
    require(source is None or (isinstance(source, dict) and text(source.get('path'))
            and type(source.get('line')) is int and source['line'] > 0), 'invalid source locator')
    for field in ('instances', 'actual_parent_edges'):
        if field in value:
            require(isinstance(value[field], list) and all(isinstance(v, dict) for v in value[field]),
                    f'{field} must be a list of locators')
    for field in ('placement', 'grouping'):
        if field in value:
            require(text(value[field]), f'invalid {field}')


def validate(catalog):
    require(isinstance(catalog, dict) and catalog.get('schema') == 1
            and isinstance(catalog.get('modules'), list), 'expected schema 1 catalog')
    evidence_table(catalog.get('evidence'))
    by_id = {}
    for row in catalog['modules']:
        require(isinstance(row, dict) and identifier(row.get('module_id')), 'invalid module ID')
        mid = row['module_id']
        require(mid not in by_id, 'duplicate ID: ' + mid)
        require(identifier(row.get('scope')) and text(row.get('name')), 'invalid identity: ' + mid)
        require(isinstance(row.get('lifecycle'), str) and row['lifecycle'] in STATES, 'invalid lifecycle: ' + mid)
        require(strings(row.get('aliases')) and strings(row.get('references')), 'invalid aliases/references: ' + mid)
        require(isinstance(row.get('tracking'), dict) and isinstance(row.get('history'), list),
                'invalid tracking/history: ' + mid)
        observations = row.get('observations')
        require(isinstance(observations, list) and observations, 'missing observations: ' + mid)
        for observation in observations:
            binding(observation)
            require(text(observation.get('baseline')) and isinstance(observation.get('baseline_sha256'), str)
                    and SHA256.fullmatch(observation['baseline_sha256']), 'missing baseline identity: ' + mid)
            evidence_refs(observation.get('evidence'), catalog['evidence'])
        for event in row['history']:
            require(isinstance(event, dict) and text(event.get('kind')) and text(event.get('reason'))
                    and text(event.get('baseline')),
                    'invalid history event: ' + mid)
            evidence_refs(event.get('evidence'), catalog['evidence'])
        by_id[mid] = row
    for mid, row in by_id.items():
        parent = row.get('parent_id')
        require('parent_id' in row and (parent is None or (isinstance(parent, str) and parent in by_id)),
                'unknown parent: ' + mid)
        if parent:
            require(by_id[parent]['scope'] == row['scope'], 'parent crosses observation scopes: ' + mid)
        seen = {mid}
        while parent:
            require(parent not in seen, 'parent cycle: ' + mid)
            seen.add(parent)
            parent = by_id[parent].get('parent_id')
            require(parent is None or (isinstance(parent, str) and parent in by_id), 'unknown ancestor: ' + mid)
        for event in row['history']:
            successors = event.get('successors', [])
            require(strings(successors) and len(successors) == len(set(successors))
                    and all(s in by_id and s != mid and by_id[s]['scope'] == row['scope'] for s in successors),
                    'invalid successors: ' + mid)
    successors = {}
    for mid, row in by_id.items():
        if row['lifecycle'] != 'active':
            latest = next((e for e in reversed(row['history']) if e['kind'] == row['lifecycle']), None)
            require(latest is not None, 'terminal lifecycle requires a recorded transition: ' + mid)
            successors[mid] = latest.get('successors', [])
    visiting, visited = set(), set()

    def visit(mid):
        require(mid not in visiting, 'successor cycle: ' + mid)
        if mid in visited:
            return
        visiting.add(mid)
        for successor in successors.get(mid, []):
            visit(successor)
        visiting.remove(mid)
        visited.add(mid)

    for mid in successors:
        visit(mid)
    return by_id


def catalog_path(project):
    value = project.config.get('modules')
    require(text(value), 'configure modules with the catalog path in root ucv.json')
    return contained(project.root, value)


def load(project):
    catalog = read(catalog_path(project))
    validate(catalog)
    return catalog


def adopt(project, snapshot, destination):
    """First adoption only: retain supplied IDs and attach existing DUTs.

    Input is a canonical catalog plus dut_modules (suite -> DUT -> module ID).
    It contains no generated hardware and cannot overwrite an existing catalog.
    """
    from .workspace import metadata
    with lock(project.root/'.cache/locks/init'), lock(project.root/'.cache/locks/modules'):
        require(read(project.root/'ucv.json') == project.config, 'project configuration changed; reload before adoption')
        require(not project.config.get('modules'), 'catalog already configured; use diff/apply')
        path = contained(project.root, destination)
        require(not path.exists() and not path.is_symlink(), 'refusing to overwrite catalog')
        require(isinstance(snapshot, dict) and set(snapshot) == {'catalog', 'dut_modules'}, 'invalid adoption snapshot')
        catalog, assignments = snapshot['catalog'], snapshot['dut_modules']
        by_id = validate(catalog)
        require(isinstance(assignments, dict) and assignments.keys() == project.config['suites'].keys(),
                'adoption must account for every configured suite')
        changes = []
        for name, mapping in assignments.items():
            suite = project.suite(name)
            require(isinstance(mapping, dict) and mapping.keys() == suite.recipe['duts'].keys(),
                    'adoption must account for every DUT: ' + name)
            meta = metadata(suite)
            for dut, mid in mapping.items():
                require(isinstance(mid, str) and mid in by_id, 'unknown adopted identity')
                require(dut in meta['duts'] and meta['duts'][dut].get('module_id', mid) == mid,
                        'refusing to replace an existing DUT identity')
                observed = current_observation(by_id[mid])
                require(observed['baseline_sha256'] == digest(suite.baseline)
                        and observed['baseline'] == suite.baseline['name']
                        and suite.recipe['duts'][dut]['top'] in observed['rtl_tops'],
                        'adopted DUT disagrees with baseline/module: ' + name + '/' + dut)
                meta['duts'][dut]['module_id'] = mid
            target = suite.path/'workspace.json'
            changes.append((target, meta, target.read_bytes()))
        config = deepcopy(project.config)
        config['modules'] = str(path.relative_to(project.root))
        target = project.root/'ucv.json'
        changes.append((target, config, target.read_bytes()))
        before = {str(p.relative_to(project.root)): file_hash(p) for p, _, _ in changes}
        written, created = [], False
        try:
            write(path, catalog)
            created = True
            for target, value, original in changes:
                write(target, value)
                written.append((target, original))
            project.config = config
            checked = check(project)
            require(not checked['errors'], 'adoption readback: ' + '; '.join(checked['errors']))
        except Exception:
            for target, original in reversed(written):
                target.write_bytes(original)
            if created and path.is_file():
                path.unlink()
            project.config = read(project.root/'ucv.json')
            raise
        return {'status': 'ADOPTED', 'modules': len(by_id),
                'duts': sum(len(v) for v in assignments.values()), 'catalog_sha256': digest(catalog),
                'previous_file_hashes': before, 'errors': checked['errors'], 'notices': checked['notices']}


def current_observation(row):
    return row['observations'][-1]


def identity_view(row):
    observed = current_observation(row)
    return {**{key: deepcopy(row[key]) for key in ('name', 'parent_id', 'lifecycle')},
            **{key: deepcopy(observed.get(key)) for key in
               ('baseline', 'baseline_sha256', 'availability', 'source', 'rtl_tops')}}


def check(project, suites=None):
    """Check identities and current DUT references; absence is not retirement."""
    catalog = load(project)
    by_id = validate(catalog)
    errors, notices, bindings = [], [], []
    from .workspace import metadata
    for suite in suites if suites is not None else [project.suite(s) for s in project.config['suites']]:
        meta = metadata(suite)
        for dut, spec in suite.recipe['duts'].items():
            entry = meta['duts'].get(dut, {})
            mid = entry.get('module_id')
            label = f'{suite.name}/{dut}'
            if not isinstance(mid, str) or mid not in by_id:
                errors.append(label + ': missing/unknown module_id')
                continue
            row = by_id[mid]
            observed = current_observation(row)
            bindings.append({'suite': suite.name, 'dut': dut, 'module_id': mid,
                             'testbench': entry.get('testbench', entry.get('module', dut))})
            if (observed['baseline'] != suite.baseline['name']
                    or observed['baseline_sha256'] != digest(suite.baseline)):
                notices.append(label + ': module observation belongs to another baseline; reobserve')
            elif observed['availability'] == 'unobserved':
                notices.append(label + ': module was not observed; last known binding retained in history')
            elif spec['top'] not in observed['rtl_tops']:
                errors.append(label + ': top is outside the observed module variants')
            elif observed['availability'] != 'present':
                notices.append(label + ': module availability=' + observed['availability'])
            if row['lifecycle'] != 'active':
                notices.append(label + ': historical binding to ' + row['lifecycle'] + ' module')
    for row in catalog['modules']:
        for ref in row['references']:
            if '://' not in ref and not contained(project.root, ref.split('#')[0]).is_file():
                from .layout import relocated_paths
                if all(p.is_file() for p in relocated_paths(project.root,ref.split('#')[0])):
                    notices.append(row['module_id'] + ': historical reference relocated: ' + ref)
                else:
                    errors.append(row['module_id'] + ': missing reference: ' + ref)
    return {'status': 'FAIL' if errors else 'PASS', 'scope': 'identity-and-bindings-only',
            'catalog_sha256': digest(catalog), 'modules': len(by_id), 'bindings': bindings,
            'errors': errors, 'notices': notices}


def init_identity(project, module_id, top, baseline):
    """Associate a new per-DUT testbench without inferring implementation reuse."""
    if not project.config.get('modules') and module_id is None:
        return
    by_id = validate(load(project))
    require(isinstance(module_id, str) and module_id in by_id, 'init requires an existing --module-id')
    row = by_id[module_id]
    observed = current_observation(row)
    require(row['lifecycle'] == 'active', 'cannot initialize a retired/superseded identity')
    require(observed['baseline_sha256'] == digest(baseline)
            and observed['baseline'] == baseline['name'], 'observe the target baseline before init')
    require(observed['availability'] in {'present', 'documented'} and top in observed['rtl_tops'],
            'new DUT top must belong to the observed module variants')


def reconcile(project, catalog, observations, decisions=None):
    """Pure proposal. Only explicit IDs/matches continue identity; similarity is a hint."""
    old = validate(catalog)
    require(isinstance(observations, dict) and observations.get('schema') == 1,
            'expected schema 1 observations')
    scope = observations.get('scope')
    require(identifier(scope), 'observations require a scope')
    baseline = project.baseline(observations.get('baseline'))
    require(observations.get('baseline_sha256') == digest(baseline), 'observation baseline hash mismatch')
    coverage = observations.get('coverage')
    require(isinstance(coverage, str) and coverage in {'complete', 'partial', 'documentation'},
            'invalid observation coverage')
    evidence_table(observations.get('evidence'))
    require(bool(observations['evidence']), 'observations require evidence hashes')
    evidence = deepcopy(catalog['evidence'])
    for key, value in observations['evidence'].items():
        require(key not in evidence or evidence[key] == value, 'cannot rewrite evidence: ' + key)
        evidence[key] = value
    evidence_ids = list(observations['evidence'])
    inputs = observations.get('modules')
    require(isinstance(inputs, list), 'observations modules must be a list')
    by_key = {}
    for row in inputs:
        require(isinstance(row, dict) and identifier(row.get('key')), 'invalid observation key')
        key = row['key']
        require(key not in by_key and text(row.get('name')), 'duplicate key or invalid name: ' + key)
        require(set(row) <= BINDING_FIELDS | {'key', 'module_id', 'name', 'parent_key', 'references'},
                'observations cannot supply tracking/lifecycle or unknown fields: ' + key)
        require('parent_key' in row and (row['parent_key'] is None or identifier(row['parent_key'])),
                'explicit parent_key required: ' + key)
        require('module_id' not in row or identifier(row['module_id']), 'invalid observation module_id')
        require(strings(row.get('references', [])), 'invalid observation references')
        binding(row)
        require(row['availability'] != 'absent' or coverage == 'complete',
                'absence requires complete observation, not partial/documentation')
        require(coverage != 'documentation' or row['availability'] in {'documented', 'unobserved'},
                'documentation is not generated hardware evidence')
        by_key[key] = row
    require(all(r['parent_key'] is None or r['parent_key'] in by_key for r in inputs),
            'parent_key must identify an observation in this input')
    decisions = decisions if decisions is not None else {'matches': {}, 'add': {}, 'transitions': []}
    require(isinstance(decisions, dict) and set(decisions) <= {'matches', 'add', 'transitions'},
            'invalid decisions object')
    matches, additions, transitions = (decisions.get('matches', {}), decisions.get('add', {}),
                                        decisions.get('transitions', []))
    require(isinstance(matches, dict) and isinstance(additions, dict) and isinstance(transitions, list),
            'invalid decisions collections')
    require(not (matches.keys() & additions.keys()) and (matches.keys() | additions.keys()) <= by_key.keys(),
            'duplicate or unused identity decisions')
    assigned, reasons, unresolved, replayed_additions = {}, {}, [], set()

    def observed_binding(value):
        observed = {k: deepcopy(value[k]) for k in BINDING_FIELDS if k in value}
        observed.update(baseline=baseline['name'], baseline_sha256=digest(baseline), evidence=evidence_ids)
        return observed

    def creation_hash(key):
        return digest({'scope': scope, 'observation': by_key[key], 'decision': additions[key],
                       'baseline': baseline, 'evidence': observations['evidence']})

    for key, row in by_key.items():
        choice = matches.get(key, additions.get(key))
        if choice is not None:
            require(isinstance(choice, dict) and set(choice) == {'module_id', 'reason'}
                    and identifier(choice.get('module_id')) and text(choice.get('reason')),
                    'identity decision needs module_id and reason: ' + key)
            mid = choice['module_id']
            if key in additions and mid in old:
                prior = old[mid]
                require(prior['lifecycle'] == 'active' and prior['name'] == row['name']
                        and current_observation(prior) == observed_binding(row)
                        and any(e.get('creation_sha256') == creation_hash(key) for e in prior['history']),
                        'invalid match/add identity; not an exact creation replay: ' + key)
                replayed_additions.add(key)
            else:
                require((mid in old) if key in matches else (mid not in old), 'invalid match/add identity: ' + key)
            reasons[key] = choice['reason']
        else:
            mid = row.get('module_id')
            reasons[key] = '延续显式持久 ID；本次观察不构成验证结果。'
        if mid not in old and key not in additions:
            candidates = []
            for candidate in old.values():
                if candidate['scope'] != scope:
                    continue
                prior = candidate['observations']
                if (row['name'] in [candidate['name'], *candidate['aliases']]
                        or any(set(row['rtl_tops']) & set(o['rtl_tops']) for o in prior)
                        or (row.get('source') and any(row['source']['path'] == (o.get('source') or {}).get('path') for o in prior))):
                    candidates.append(candidate['module_id'])
            unresolved.append({'key': key, 'kind': 'identity-review', 'candidates': candidates})
            continue
        require(mid not in assigned.values(), 'multiple observations resolve to one ID: ' + str(mid))
        require(mid not in old or old[mid]['scope'] == scope, 'identity cannot cross scopes: ' + str(mid))
        assigned[key] = mid
    # A missing parent decision must not silently turn a child into a root.
    for key, row in by_key.items():
        if key in assigned and row['parent_key'] is not None and row['parent_key'] not in assigned:
            unresolved.append({'key': key, 'kind': 'unresolved-parent', 'parent_key': row['parent_key']})
    for key in replayed_additions:
        require(old[assigned[key]]['parent_id'] == assigned.get(by_key[key]['parent_key']),
                'creation replay cannot change parent identity')
    report = {'status': 'NEEDS_REVIEW' if unresolved else 'READY', 'scope': scope,
              'catalog_sha256': digest(catalog), 'observations_sha256': digest(observations),
              'decisions_sha256': digest(decisions), 'changes': [], 'unresolved': unresolved}
    report['plan_sha256'] = digest({k: report[k] for k in
                                    ('catalog_sha256', 'observations_sha256', 'decisions_sha256')})
    if unresolved:
        for key, mid in assigned.items():
            value = by_key[key]
            report['changes'].append({'module_id': mid, 'kinds': ['pending-observation'],
                                      'before': identity_view(old[mid]) if mid in old else None,
                                      'after': {'name': value['name'], 'parent_key': value['parent_key'],
                                                'baseline': baseline['name'],
                                                **{k: deepcopy(value[k]) for k in BINDING_FIELDS if k in value}}})
        for mid, row in old.items():
            if row['scope'] == scope and mid not in assigned.values() and row['lifecycle'] == 'active':
                report['changes'].append({'module_id': mid, 'kinds': ['unobserved-pending-identity-review'],
                                          'before': identity_view(row)})
        return report, None
    updated = deepcopy(catalog)
    updated['evidence'] = evidence
    result = {row['module_id']: row for row in updated['modules']}
    baseline_name = baseline['name']

    def event(row, kind, reason, **extra):
        row['history'].append({'kind': kind, 'baseline': baseline_name, 'reason': reason,
                               'evidence': evidence_ids, **extra})

    for key, value in by_key.items():
        mid = assigned[key]
        parent_id = assigned.get(value['parent_key'])
        observed = observed_binding(value)
        if mid not in result:
            row = {'module_id': mid, 'scope': scope, 'name': value['name'], 'parent_id': parent_id,
                   'lifecycle': 'active', 'aliases': [], 'references': value.get('references', []),
                   'tracking': {}, 'observations': [observed], 'history': []}
            result[mid] = row
            updated['modules'].append(row)
            event(row, 'added', reasons[key], creation_sha256=creation_hash(key))
            report['changes'].append({'module_id': mid, 'kinds': ['added'], 'before': None,
                                      'after': identity_view(row), 'reason': reasons[key]})
            continue
        row = result[mid]
        kinds = []
        before = identity_view(row)
        if row['name'] != value['name']:
            kinds.append('renamed')
            row['aliases'] = list(dict.fromkeys([*row['aliases'], row['name']]))
            row['name'] = value['name']
        if row['parent_id'] != parent_id:
            kinds.append('moved')
            row['parent_id'] = parent_id
        previous = current_observation(row)
        if observed != previous:
            kinds.append('baseline-changed' if observed['baseline_sha256'] != previous['baseline_sha256']
                         else 'binding-changed')
            if observed.get('source') != previous.get('source'):
                kinds.append('source-changed')
            if observed['rtl_tops'] != previous['rtl_tops']:
                kinds.append('variants-changed')
            row['observations'].append(observed)
        refs = list(dict.fromkeys([*row['references'], *value.get('references', [])]))
        if row['references'] != refs:
            kinds.append('references-added')
            row['references'] = refs
        if kinds:
            event(row, 'observed', reasons[key], before=before)
            report['changes'].append({'module_id': mid, 'kinds': kinds, 'before': before,
                                      'after': identity_view(row), 'reason': reasons[key]})
    # Old IDs absent from a new snapshot remain visible. Never infer retirement,
    # nor copy their last-known top into a new-baseline hardware observation.
    for mid, row in result.items():
        if row['scope'] != scope or mid in assigned.values() or row['lifecycle'] != 'active':
            continue
        missing = {'baseline': baseline_name, 'baseline_sha256': digest(baseline),
                   'availability': 'unobserved', 'source': None, 'rtl_tops': [], 'evidence': evidence_ids}
        if current_observation(row) != missing:
            before = identity_view(row)
            row['observations'].append(missing)
            event(row, 'unobserved', f'本次 {coverage} 观察未包含此 ID；保留上次绑定，待核实。')
            report['changes'].append({'module_id': mid, 'kinds': ['unobserved'],
                                      'before': before, 'after': identity_view(row)})
    transitioned = set()
    for change in transitions:
        require(isinstance(change, dict) and set(change) == {'module_id', 'kind', 'successors', 'reason'},
                'transition requires module_id/kind/successors/reason')
        mid, kind = change['module_id'], change['kind']
        require(isinstance(mid, str) and mid in old and mid not in transitioned, 'unknown/duplicate transition ID')
        require(isinstance(kind, str) and kind in STATES and text(change['reason']) and strings(change['successors']),
                'invalid transition')
        row = result[mid]
        require(row['scope'] == scope, 'transition crosses scopes')
        require(bool(change['successors']) == (kind not in {'active', 'retired'}), 'invalid transition successors')
        if kind != 'active':
            require(not (mid in assigned.values() and current_observation(row)['availability'] == 'present'),
                    'superseded identity still observed present; resolve its scope first')
        transitioned.add(mid)
        if row['lifecycle'] != kind or not row['history'] or row['history'][-1].get('successors') != change['successors']:
            before = row['lifecycle']
            row['lifecycle'] = kind
            event(row, kind, change['reason'], previous_lifecycle=before, successors=change['successors'])
            report['changes'].append({'module_id': mid, 'kinds': [kind], 'successors': change['successors']})
    for mid in assigned.values():
        if mid in old and old[mid]['lifecycle'] != 'active':
            require(result[mid]['lifecycle'] == 'active' or current_observation(result[mid])['availability'] != 'present',
                    'reactivation requires an explicit active transition')
    validate(updated)
    return report, updated


def diff(project, observations, decisions=None):
    return reconcile(project, load(project), observations, decisions)[0]


def apply(project, observations, decisions, expected):
    with lock(project.root/'.cache/locks/modules'):
        report, updated = reconcile(project, load(project), observations, decisions)
        require(report['plan_sha256'] == expected, 'stale diff; catalog, observations or decisions changed')
        require(updated is not None, 'unresolved identities; review diff candidates before applying')
        if report['changes']:
            write(catalog_path(project), updated)
        require(load(project) == updated, 'catalog readback mismatch')
        return {**report, 'status': 'APPLIED', 'updated': bool(report['changes']),
                'result_sha256': digest(updated)}


def tree(project, catalog=None):
    catalog = load(project) if catalog is None else catalog
    by_id = validate(catalog)
    from .workspace import metadata
    bindings = {}
    for name in project.config['suites']:
        suite = project.suite(name)
        for dut, entry in metadata(suite)['duts'].items():
            bindings.setdefault(entry.get('module_id'), []).append(f'{name}/{dut}')
    children = {}
    for row in catalog['modules']:
        children.setdefault(row['parent_id'], []).append(row)
    lines = ['# 模块树', '', '模块身份与绑定导航；生命周期和接入观察均不是硬件验收结果。', '', '```text']

    def visit(row, depth):
        observation = current_observation(row)
        duts = ', '.join(bindings.get(row['module_id'], [])) or '无独立 DUT'
        lines.append('  '*depth + f"{row['name']} [{row['module_id']}] — {duts}；"
                     f"{row['lifecycle']}/{observation['availability']} @ {observation['baseline']}")
        for child in children.get(row['module_id'], []):
            visit(child, depth+1)

    for row in children.get(None, []):
        visit(row, 0)
    lines += ['```', '', f'记录数：{len(by_id)}。每个 DUT 的资料与选跑入口用 `ucv info <suite> --dut <dut>` 查询。']
    return '\n'.join(lines)
