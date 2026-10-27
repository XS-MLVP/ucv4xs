"""Only the known useful-only mismatch may be re-labelled; others propagate."""
from types import SimpleNamespace

from bpuverify.tage.case.way_migration_scenario import MisassociatedProviderUseful
from bpuverify.tage.case.way_migration_scenario import as_misassociated_useful


def error(*paths):
    """The helper only consumes the difference paths, not the board object."""
    return SimpleNamespace(differences=tuple(SimpleNamespace(path=path) for path in paths))


def test_useful_only_mismatch_becomes_the_declared_defect():
    translated = as_misassociated_useful(error("0.useful"))
    assert isinstance(translated, MisassociatedProviderUseful)
    assert "0.useful" in str(translated)


def test_mixed_or_empty_mismatch_is_not_relabelled():
    assert as_misassociated_useful(error("0.useful", "0.counter")) is None
    assert as_misassociated_useful(error("0.counter")) is None
    assert as_misassociated_useful(error()) is None
