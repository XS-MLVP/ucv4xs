"""Fixed arithmetic answers qualify the oracle, not hardware coverage."""
import pytest

from suites.vector.vagq.addrgen.reference import AddressContext, IndexedAddress, StridedAddress, address

pytestmark = pytest.mark.toffee_functional_coverage(False)


@pytest.mark.parametrize('transaction,expected', [
    (StridedAddress(AddressContext(0x1000, 2, 1), 3), 0x1009),
    (StridedAddress(AddressContext(0x1000, 64, 0, 8, 3), 4), 0x1118),
    (StridedAddress(AddressContext(2, 1, 0), -4), (1 << 64) - 2),
    (IndexedAddress(AddressContext(0x1000, 3, 0, 2, 3), tuple(range(16))), 0x1009),
    (IndexedAddress(AddressContext(0, 1, 1), (0x8000000000000000, 7)), 0x8000000000000000),
])
def test_fixed_independent_addresses(transaction, expected):
    assert address(transaction) == expected


@pytest.mark.parametrize('indices', [(1,), (0, 1 << 64)])
def test_invalid_indices_are_rejected(indices):
    with pytest.raises(ValueError):
        IndexedAddress(AddressContext(0, 0, 0), indices)
