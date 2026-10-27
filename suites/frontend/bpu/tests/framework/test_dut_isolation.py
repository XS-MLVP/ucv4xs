"""Collection and process ownership are independent of SDK handle casting."""
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest

from bpuverify.common.env.process_scope import DOMAINS, DutProcessScope
from bpuverify.common.pytest.isolation import collection_index, item_scope, selected_ids


def item(node='tests/framework/test_owner.py::test_case', *, fixtures=(), marker=None):
    markers = [] if marker is None else [NS(args=(marker,), kwargs={})]
    return NS(nodeid=node, fixturenames=list(fixtures),
              iter_markers=lambda name: iter(markers if name == 'dut' else ()))


@pytest.mark.parametrize('domain', DOMAINS)
def test_a_finished_instance_does_not_allow_a_different_native_package(domain):
    scope = DutProcessScope(domain)
    scope.claim(domain)
    scope.claim(domain)
    assert scope.owner == domain and scope.claims == 2
    other = 'ras' if domain == 'bpu' else 'bpu'
    with pytest.raises(RuntimeError, match='cannot load'):
        scope.claim(other)
    assert scope.owner == domain and scope.claims == 2


@pytest.mark.parametrize('domain', DOMAINS)
def test_unconfigured_direct_pytest_still_cannot_switch_generated_dut_type(domain):
    scope = DutProcessScope()
    scope.claim(domain)
    other = 'ras' if domain == 'bpu' else 'bpu'
    with pytest.raises(RuntimeError, match='new interpreter'):
        scope.claim(other)


@pytest.mark.parametrize('domain', DOMAINS)
def test_pure_worker_rejects_a_native_dut_before_import(domain):
    with pytest.raises(RuntimeError, match='cannot load'):
        DutProcessScope('pure').claim(domain)


@pytest.mark.parametrize('domain', DOMAINS)
def test_collection_uses_transitive_factory_and_agent_ownership(domain):
    native = item(f'tests/{domain}/testcase/test_x.py::test_x',
                  fixtures=('dut_factory', f'{domain}_agent'))
    assert item_scope(native) == domain
    pure = item(f'tests/{domain}/scoreboard/test_x.py::test_x', fixtures=('monkeypatch',))
    assert item_scope(pure) == 'pure'


@pytest.mark.parametrize('domain', DOMAINS)
def test_framework_native_parameters_need_explicit_dut_ownership(domain):
    assert item_scope(item(fixtures=('dut_factory',), marker=domain)) == domain
    with pytest.raises(ValueError, match='explicit and unique'):
        item_scope(item(fixtures=('dut_factory',)))


@pytest.mark.parametrize('domain', DOMAINS)
def test_native_module_directory_and_marker_must_agree(domain):
    other = 'ras' if domain == 'bpu' else 'bpu'
    with pytest.raises(ValueError, match='explicit and unique'):
        item_scope(item(f'tests/{domain}/testcase/test_x.py::test_x',
                        fixtures=('dut_factory',), marker=other))


def test_dut_marker_without_a_factory_is_not_silently_considered_hardware():
    with pytest.raises(ValueError, match='without factory'):
        item_scope(item(marker='bpu'))


@pytest.mark.parametrize('invalid', ('', 'unknown', 'BPU', 1, None))
def test_unknown_dut_claims_fail_closed(invalid):
    with pytest.raises(ValueError, match='unknown DUT'):
        DutProcessScope().claim(invalid)


@pytest.mark.parametrize('retained', ('package', 'native-mapping', 'both'))
def test_retained_foreign_packages_and_native_mappings_are_detected(tmp_path, retained):
    names = ('kunminghu_v3_pytest_ras_0.xspcomm.pyxspcomm',) if retained != 'native-mapping' else ()
    maps = f'1000-2000 r-xp 0000 08:02 1234 {tmp_path}/ras/native.so\n' if retained != 'package' else ''
    with pytest.raises(RuntimeError, match='loaded DUTs'):
        DutProcessScope('bpu').observe(names=names, maps=maps, dut_root=tmp_path)


@pytest.mark.parametrize('domain', DOMAINS)
def test_own_libraries_and_python_wrappers_are_not_foreign(tmp_path, domain):
    names = (f'kunminghu_v3_pytest_{domain}_0.xspcomm.pyxspcomm',)
    maps = f'1000-2000 r-xp 0000 08:02 1234 {tmp_path}/{domain}/native.so\n'
    scope = DutProcessScope(domain)
    scope.claim(domain)
    assert scope.observe(names=names, maps=maps, dut_root=tmp_path) == dict(
        packages=[domain], native_mappings=[domain], owner=domain, claims=1)


def test_partition_is_a_disjoint_complete_permutation_not_a_selection_heuristic():
    values = [item(), *[item(f'tests/{name}/testcase/test_x.py::test_x',
        fixtures=('dut_factory', f'{name}_agent')) for name in DOMAINS]]
    index = collection_index(values)
    groups = [selected_ids(index, name) for name in ('pure', *DOMAINS)]
    assert sum(map(len, groups)) == len(values)
    assert set(node for group in groups for node in group) == {value.nodeid for value in values}
    assert all(len(group) == 1 for group in groups)


@pytest.mark.parametrize('fault', ('hash', 'count', 'duplicate', 'scope', 'version'))
def test_changed_partition_index_is_rejected(fault):
    index = deepcopy(collection_index([item()]))
    if fault == 'hash': index['collection_sha256'] = 'changed'
    elif fault == 'count': index['count'] += 1
    elif fault == 'duplicate': index['cases'] *= 2
    elif fault == 'scope': index['cases'][0]['scope'] = 'unknown'
    else: index['version'] = 2
    with pytest.raises(ValueError, match='partition'):
        selected_ids(index, 'pure')


def test_duplicate_or_empty_collection_is_not_a_valid_plan():
    with pytest.raises(ValueError, match='empty or duplicate'):
        collection_index([])
    value = item()
    with pytest.raises(ValueError, match='empty or duplicate'):
        collection_index([value, value])
