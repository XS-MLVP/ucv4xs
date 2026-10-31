"""Renamed Python distributions must be read from the lock, not guessed."""
from importlib.metadata import PackageNotFoundError

from ucv.runtime import distribution_name
from ucv.runtime import installed_version


def test_distribution_name_prefers_the_locked_name():
    assert distribution_name({'distribution': 'uc-toffee'}, 'pytoffee') == 'uc-toffee'
    assert distribution_name({}, 'pytoffee') == 'pytoffee'


def test_installed_version_uses_the_locked_distribution(monkeypatch):
    seen = []

    def version(name):
        seen.append(name)
        return {'uc-toffee': '2.1.0'}[name]

    monkeypatch.setattr('ucv.runtime.version', version)
    assert installed_version({'distribution': 'uc-toffee'}, 'pytoffee') == '2.1.0'
    assert seen == ['uc-toffee']


def test_installed_version_falls_back_for_legacy_installations(monkeypatch):
    def version(name):
        if name == 'pytoffee':
            return '2.0.1'
        raise PackageNotFoundError(name)

    monkeypatch.setattr('ucv.runtime.version', version)
    assert installed_version({'distribution': 'uc-toffee'}, 'pytoffee') == '2.0.1'


def test_missing_distribution_fails_closed(monkeypatch):
    def missing(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr('ucv.runtime.version', missing)
    try:
        installed_version({'distribution': 'uc-toffee'}, 'pytoffee')
    except RuntimeError as error:
        assert 'installed distribution missing' in str(error)
    else:
        raise AssertionError('a missing locked distribution must fail')
