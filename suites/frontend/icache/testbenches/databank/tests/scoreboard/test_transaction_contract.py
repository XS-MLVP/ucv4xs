"""Domain and snapshot selftests, not additional SRAM functional credit."""
from dataclasses import FrozenInstanceError, replace
import pytest
from suites.frontend.icache.testbenches.databank.env.agent.main import DataBankAgent
from suites.frontend.icache.testbenches.databank.transactions.types import BankBist
from suites.frontend.icache.testbenches.databank.transactions.types import BankCycle
from suites.frontend.icache.testbenches.databank.transactions.types import BankPortRead
from suites.frontend.icache.testbenches.databank.transactions.types import BankRead
from suites.frontend.icache.testbenches.databank.transactions.types import BankWrite
from suites.frontend.icache.testbenches.databank.transactions.types import BankReadData
from suites.frontend.icache.testbenches.databank.transactions.types import BankObservation
from suites.frontend.icache.testbenches.databank.transactions.types import BankReadResult
from suites.frontend.icache.testbenches.databank.transactions.types import StorageOrigin
from suites.frontend.icache.testbenches.databank.env.bundle.abi import expected_schema
from suites.frontend.icache.testbenches.databank.env.bundle.abi import validate_schema

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize("index", (-1, 256, True, 1.5, None))
def test_read_rejects_non_physical_set_before_an_input_can_be_driven(index):
    with pytest.raises(ValueError):
        BankRead(index)


@pytest.mark.parametrize("field,value", (
    ("set_index", 256), ("set_index", True), ("waymask", 16), ("waymask", -1),
    ("waymask", True), ("data", 1 << 64), ("data", -1), ("data", True), ("code", 2), ("code", True),
))
def test_write_domain_cannot_rely_on_signal_truncation(field, value):
    values = dict(set_index=255, waymask=15, data=(1 << 64) - 1, code=1)
    values[field] = value
    with pytest.raises(ValueError):
        BankWrite(**values)


def test_zero_waymask_and_full_width_storage_word_remain_legal():
    assert BankWrite(255, 0, (1 << 64) - 1, 1).waymask == 0
    assert BankRead(0).set_index == 0


def test_response_snapshot_is_detached_and_deeply_immutable():
    data, codes = [1, 2, 3, 4], [0, 1, 0, 1]
    snapshot = BankReadData(data, codes)
    data[0], codes[1] = 99, 0
    assert snapshot.data == (1, 2, 3, 4) and snapshot.code == (0, 1, 0, 1)
    with pytest.raises((FrozenInstanceError, AttributeError)):
        snapshot.data = (0,) * 4


@pytest.mark.parametrize("data,code", (
    ((1,), (0,)), ((0,) * 4, (0,) * 3), ((0,) * 3 + (-1,), (0,) * 4), ((0,) * 4, (0,) * 3 + (2,)),
))
def test_incomplete_or_malformed_response_is_not_an_inactive_way(data, code):
    with pytest.raises(ValueError):
        BankReadData(data, code)


@pytest.mark.parametrize("sets,ways", ((128, 4), (256, 2), (True, 4), (256, True)))
def test_wrong_model_geometry_is_rejected_before_native_binding(sets, ways):
    with pytest.raises(ValueError, match="DefaultConfig"):
        DataBankAgent(None, sets=sets, ways=ways)


@pytest.mark.parametrize("operation", ("read", "write"))
async def test_public_operation_checks_domain_before_touching_a_driver(operation):
    # No drivers or native DUT are installed. Rejection cannot be caused by
    # truncated XData, a later model error or an unavailable native signal.
    agent = object.__new__(DataBankAgent)
    with pytest.raises(ValueError, match="8-bit"):
        if operation == "read":
            await agent.read(256)
        else:
            await agent.write(256, 15, data=0)


@pytest.mark.parametrize('field,width', (('array', 3), ('all_arrays', 1), ('readen', 1),
    ('writeen', 1), ('be', 1), ('addr', 9), ('addr_rd', 9), ('indata', 66)))
@pytest.mark.parametrize('bad', ('bool', 'negative', 'wide'))
def test_mbist_domain_is_strict_without_narrowing_physical_encodings(field, width, bad):
    value = True if bad == 'bool' else -1 if bad == 'negative' else 1 << width
    with pytest.raises(ValueError):
        replace(BankBist(), **{field: value})


def test_mbist_full_width_address_aliases_and_inapplicable_masks_remain_legal():
    request = BankBist(array=7, all_arrays=1, readen=1, writeen=1, be=0,
                       addr=511, addr_rd=511, indata=(1 << 66) - 1)
    assert request.addr_rd == 511 and request.be == 0
    assert BankBist(array=0).array == 0
    indices = [0, 1, 254, 255]
    request = BankPortRead(indices, 0)
    indices[0] = 99
    assert request.set_indices == (0, 1, 254, 255)


@pytest.mark.parametrize('indices,mask', (([0] * 3, 15), ([0, 0, 0, 256], 15),
    ([0, 0, 0, True], 15), ([0] * 4, 16), ([0] * 4, True)))
def test_per_way_request_requires_complete_immutable_addresses_and_exact_mask(indices, mask):
    with pytest.raises(ValueError):
        BankPortRead(indices, mask)


@pytest.mark.parametrize('role', ('read', 'write', 'bist'))
def test_cycle_rejects_raw_dictionaries_before_any_driver_access(role):
    with pytest.raises(ValueError):
        BankCycle(**{role: {}})


@pytest.mark.parametrize('leaf', ('read.setIdx[3]', 'mbist.addr', 'mbist_response.outdata',
                                'response[3].code', 'sram_control.ways[3].hold'))
@pytest.mark.parametrize('fault', ('missing', 'width', 'boolean-width'))
def test_live_and_schema_cannot_agree_on_an_incomplete_defaultconfig_abi(leaf, fault):
    actual = expected_schema()
    if fault == 'missing':
        actual.pop(leaf)
    else:
        actual[leaf] = True if fault == 'boolean-width' else actual[leaf] + 1
    with pytest.raises(ValueError, match='ABI'):
        validate_schema(actual)


def test_observation_and_source_receipts_detach_all_nested_identity_containers():
    sources = [StorageOrigin(3, 1, 'write', 4, 7, way) for way in range(4)]
    result = BankReadResult(5, 1, 8, 8, BankReadData((7,) * 4, (0,) * 4), sources)
    sources[0] = StorageOrigin(99, 1, 'bist', 4, 7, 0)
    results, uids = [result], [5]
    observation = BankObservation(8, 1, 1, result.values, 0, 0, uids, uids, results)
    results.clear()
    uids[0] = 99
    assert observation.responses == (result,) and observation.accepted == (5,)
    assert observation.responses[0].sources[0].uid == 3
    with pytest.raises(FrozenInstanceError):
        observation.responses[0].sources[0].uid = 99
