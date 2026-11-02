"""MetaBank schema/domain controls; unique module name across pytest subtrees."""
from dataclasses import replace, FrozenInstanceError
import pytest
from suites.frontend.icache.metabank.agent.main import MetaBankAgent
from suites.frontend.icache.metabank.bundle.abi import expected_schema, validate_schema
from suites.frontend.icache.metabank.transaction.types import (
    MetaBankRead, MetaBankWrite, MetaBankWay, MetaBankBist, MetaBankCycle,
    MetaOrigin, MetaReadResult, MetaObservation)

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize('factory,field,width', (
    (lambda: MetaBankRead(0), 'set_index', 7),
    (lambda: MetaBankWrite(0, 15, 0), 'set_index', 7),
    (lambda: MetaBankWrite(0, 15, 0), 'waymask', 4),
    (lambda: MetaBankWrite(0, 15, 0), 'phy_tag', 36),
    (lambda: MetaBankWrite(0, 15, 0), 'maybe_rvc_map', 32),
    (lambda: MetaBankWrite(0, 15, 0), 'code', 1),
    (lambda: MetaBankWay(0, 0, 0, 0), 'valid', 1),
    (lambda: MetaBankWay(0, 0, 0, 0), 'phy_tag', 36),
    (lambda: MetaBankWay(0, 0, 0, 0), 'maybe_rvc_map', 32),
    (lambda: MetaBankWay(0, 0, 0, 0), 'code', 1),
))
@pytest.mark.parametrize('bad', ('bool', 'negative', 'wide'))
def test_functional_domain_requires_exact_physical_encodings(factory, field, width, bad):
    value = True if bad == 'bool' else -1 if bad == 'negative' else 1 << width
    with pytest.raises(ValueError):replace(factory(), **{field: value})


@pytest.mark.parametrize('field,width', (('array', 1), ('all_arrays', 1), ('readen', 1),
    ('writeen', 1), ('be', 2), ('addr', 8), ('addr_rd', 8), ('indata', 138)))
@pytest.mark.parametrize('bad', ('bool', 'negative', 'wide'))
def test_mbist_domain_cannot_be_silently_truncated_or_assumed_zero_width(field, width, bad):
    value = True if bad == 'bool' else -1 if bad == 'negative' else 1 << width
    with pytest.raises(ValueError):replace(MetaBankBist(), **{field: value})


def test_last_macro_masks_zero_and_maximal_words_remain_legal():
    assert MetaBankBist(array=1, be=0, addr=255, addr_rd=255, indata=(1 << 138) - 1).array == 1
    assert MetaBankWrite(127, 0, (1 << 36) - 1, (1 << 32) - 1, 1).waymask == 0
    assert MetaBankCycle(read=MetaBankRead(127), write=MetaBankWrite(127, 15, 7), flush_all=1)


@pytest.mark.parametrize('role', ('read', 'write', 'bist', 'flush_all'))
def test_cycle_rejects_untyped_protocol_dictionaries(role):
    with pytest.raises(ValueError):MetaBankCycle(**{role: {}})


@pytest.mark.parametrize('sets,ways', ((64, 4), (128, 2), (True, 4), (128, True)))
def test_wrong_geometry_is_rejected_before_native_binding(sets, ways):
    with pytest.raises(ValueError, match='DefaultConfig'):MetaBankAgent(None, sets=sets, ways=ways)


@pytest.mark.parametrize('operation', ('read', 'write', 'bist', 'reset'))
async def test_invalid_request_cannot_touch_a_driver_or_model(operation):
    agent = object.__new__(MetaBankAgent)
    with pytest.raises(ValueError):
        if operation == 'read':await agent.read(128)
        elif operation == 'write':await agent.write(0, 16, phy_tag=0)
        elif operation == 'bist':await agent.bist_command(indata=1 << 138)
        else:await agent.reset(True)


@pytest.mark.parametrize('leaf', ('mbist.array', 'mbist.indata', 'mbist.addr', 'write.phyTag',
    'response[3].bits.meta.maybeRvcMap', 'sram_control.ways[1].mcp_hold'))
@pytest.mark.parametrize('fault', ('missing', 'width', 'bool-width'))
def test_metadata_and_live_binding_cannot_agree_on_the_wrong_defaultconfig_abi(leaf, fault):
    actual = expected_schema()
    if fault == 'missing':actual.pop(leaf)
    else:actual[leaf] = True if fault == 'bool-width' else actual[leaf] + 1
    with pytest.raises(ValueError, match='ABI'):validate_schema(actual)


def test_response_and_both_ancestries_detach_nested_containers():
    values = [MetaBankWay(1, 7, 8, 1)] * 4
    sources = [MetaOrigin(1, 1, 'write', 4, 9, way) for way in range(4)]
    result = MetaReadResult(3, 1, 6, 6, values, sources, sources)
    uid, responses = [3], [result]
    observed = MetaObservation(6, 1, 1, values, 0, 0, uid, uid, responses)
    values[0] = MetaBankWay(1, 99, 8, 1)
    sources[0] = MetaOrigin(99, 1, 'bist', 4, 9, 0)
    uid[0] = 99;responses.clear()
    assert observed.entries[0].phy_tag == 7 and observed.responses == (result,)
    assert result.storage_sources[0].uid == result.validity_sources[0].uid == 1
    with pytest.raises(FrozenInstanceError):result.storage_sources[0].uid = 99
