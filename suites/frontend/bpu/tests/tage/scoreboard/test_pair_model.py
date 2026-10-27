import pytest

from bpuverify.tage.model.pair import TagePairModel
from bpuverify.tage.model.pair import TageTableState


@pytest.mark.parametrize('direction', (0, 1))
@pytest.mark.parametrize('alternate_way', (0, 1))
@pytest.mark.parametrize('provider_way', (0, 1))
def test_pair_initialization_is_independent_of_observed_counters(direction, alternate_way, provider_way):
    model = TagePairModel(direction, alternate_way=alternate_way, provider_way=provider_way)
    assert model.tables == (None, None, TageTableState(1 << alternate_way, 6 if direction else 1, 3),
                            TageTableState(1 << provider_way, 3 if direction else 4, 0))
    assert (model.metadata['useProvider'], model.metadata['altConf'], model.taken) == (0, 1, direction)


@pytest.mark.parametrize('direction', (0, 1))
def test_selected_alternate_updates_once_then_strong_provider_holds_it(direction):
    model = TagePairModel(direction, alternate_way=1, provider_way=0)
    model.apply(1-direction)
    assert model.provider.counter == (2 if direction else 5)
    assert model.provider.useful == 1 and model.alternate.useful == 3
    assert model.alternate.counter == (5 if direction else 2)
    assert model.selectors == (16, 15) and model.metadata['useProvider'] == 1
    for _ in range(8):
        model.apply(1-direction)
    assert model.provider.counter == (0 if direction else 7)
    assert model.provider.useful == 3 and model.alternate.counter == (5 if direction else 2)
    model.apply(direction)
    assert model.provider.counter == (1 if direction else 6)
    assert model.alternate.counter == (5 if direction else 2) and model.provider.useful == 3


@pytest.mark.parametrize('direction', (0, 1))
def test_alternate_correct_feedback_saturates_only_while_selected(direction):
    model = TagePairModel(direction, alternate_way=0, provider_way=1)
    model.apply(direction)
    assert model.alternate.counter == (7 if direction else 0)
    assert model.provider.counter == (4 if direction else 3)
    assert model.selectors == (16, 17) and model.provider.useful == 0
    model.apply(direction)
    assert model.provider.counter == (5 if direction else 2)
    assert model.alternate.counter == (7 if direction else 0)
    model.apply(direction)
    assert model.alternate.counter == (7 if direction else 0) and model.metadata['useProvider'] == 1


@pytest.mark.parametrize('direction', (0, 1))
def test_weak_alternate_confidence_selects_a_different_selector_bucket(direction):
    model = TagePairModel(direction, alternate_way=0, provider_way=1)
    for _ in range(4):
        model.apply(1-direction)
    for _ in range(3):
        model.apply(direction)
    assert model.provider.counter == (3 if direction else 4) and model.metadata['useProvider'] == 1
    model.apply(direction)
    assert model.metadata['useProvider'] == 0 and model.selectors == (16, 16)
    model.apply(1-direction)
    assert model.alternate.counter == (4 if direction else 3) and model.metadata['altConf'] == 0
    model.apply(1-direction)
    assert model.alternate.counter == (3 if direction else 4) and model.selectors == (15, 16)
    assert model.metadata['useProvider'] == 1


@pytest.mark.parametrize('direction', (0, 1))
def test_unqualified_feedback_keeps_all_pair_and_selector_state(direction):
    model = TagePairModel(direction, alternate_way=1, provider_way=0)
    before = model.tables, model.selectors
    model.apply(1-direction, qualified=False)
    assert (model.tables, model.selectors) == before


@pytest.mark.parametrize('direction, alternate_way, provider_way', ((2, 0, 0), (0, -1, 0), (0, 0, 2)))
def test_bad_initial_pair_is_rejected(direction, alternate_way, provider_way):
    with pytest.raises(ValueError):
        TagePairModel(direction, alternate_way=alternate_way, provider_way=provider_way)


@pytest.mark.parametrize('actual, qualified', ((2, True), (0, 2)))
def test_bad_update_is_atomic(actual, qualified):
    model = TagePairModel(0, alternate_way=0, provider_way=0)
    before = model.tables, model.selectors
    with pytest.raises(ValueError):
        model.apply(actual, qualified=qualified)
    assert (model.tables, model.selectors) == before
