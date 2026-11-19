"""A host without RTL generation tools must be able to take a released package.

CIRCT publishes no linux-arm64 firtool, so on aarch64 the whole-chip generation
cache never exists. ``obtain_rtl`` must then use the release and must not call
``generate``, which would fail on the missing firtool after hours of setup.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from ucv import sources
from ucv.common import UcvError, digest


def suite_for(tmp_path, name='public-test'):
    baseline = {
        'schema': 1, 'name': name,
        'repository': 'https://example.test/XiangShan.git',
        'commit': 'a' * 40, 'visibility': 'public',
        'recursive_submodules': [], 'design': {'config': 'DefaultConfig'},
        'patches': [], 'tools': {'firtool': '1.149.0'}, 'firtool_options': [],
    }
    root = tmp_path / 'project'
    (root / 'baselines').mkdir(parents=True)
    (root / '.cache').mkdir()
    return SimpleNamespace(root=root, baseline=baseline)


@pytest.fixture
def released(tmp_path, monkeypatch):
    """A release path plus a generation function that fails if it is reached."""
    suite = suite_for(tmp_path)
    rtl = tmp_path / 'release' / 'rtl'
    rtl.mkdir(parents=True)

    def fake_fetch(project, baseline, archive=None):
        return rtl

    def fake_release_spec(project, baseline):
        return {'package': 'synthetic-rtl', 'url': 'https://example.test/x.tar.gz',
                'sha256': '0' * 64}

    def forbidden_generate(project, target):
        raise AssertionError('generate must not run without a generation cache')

    monkeypatch.setattr('ucv.releases.fetch_release', fake_fetch)
    monkeypatch.setattr('ucv.releases.release_spec', fake_release_spec)
    monkeypatch.setattr('ucv.releases.release_directory', lambda project, baseline: rtl.parent)
    monkeypatch.setattr(sources, 'generate', forbidden_generate)
    return suite, rtl


@pytest.mark.parametrize('mode', ['release', 'auto'])
def test_release_is_used_without_a_local_generation(released, mode):
    suite, rtl = released
    path, origin = sources.obtain_rtl(SimpleNamespace(root=suite.root), suite, mode)
    assert path == rtl
    assert origin['kind'] == 'release'
    assert origin['release']['package'] == 'synthetic-rtl'
    assert origin['receipt'].endswith('release.json')


def test_explicit_source_still_requires_generation(released):
    """--rtl-source source must not silently fall back to the release."""
    suite, _ = released
    with pytest.raises(AssertionError, match='generate must not run'):
        sources.obtain_rtl(SimpleNamespace(root=suite.root), suite, 'source')


def test_unknown_source_mode_is_rejected(released):
    suite, _ = released
    with pytest.raises(UcvError, match='Unknown RTL source'):
        sources.obtain_rtl(SimpleNamespace(root=suite.root), suite, 'assembly')


def test_cross_check_runs_only_when_both_providers_exist(tmp_path, monkeypatch):
    """Both providers present: the release must still agree byte for byte."""
    suite = suite_for(tmp_path)
    generated = suite.root / '.cache/generated' / digest(sources.generation_spec(suite.baseline))
    generated.mkdir(parents=True)
    (generated / 'generation.json').write_text('{}')
    rtl = tmp_path / 'release' / 'rtl'
    rtl.mkdir(parents=True)
    checked = []
    monkeypatch.setattr('ucv.releases.fetch_release', lambda *args, **kwargs: rtl)
    monkeypatch.setattr('ucv.releases.release_spec',
                        lambda project, baseline: {'package': 'x'})
    monkeypatch.setattr('ucv.releases.release_directory', lambda project, baseline: rtl.parent)
    monkeypatch.setattr(sources, 'generate', lambda project, target: generated / 'rtl')
    monkeypatch.setattr(sources, 'compare_rtl',
                        lambda left, right: checked.append((left, right)))
    sources.obtain_rtl(SimpleNamespace(root=suite.root), suite, 'release')
    assert checked == [(generated, rtl)]
