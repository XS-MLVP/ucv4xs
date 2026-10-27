"""Flat wire encoding is qualified independently from permit semantics."""
import pytest

from vagqverify.ordered.encoding import encode
from vagqverify.ordered.types import Beat, Entry, Redirect, SplitDone

pytestmark = pytest.mark.toffee_functional_coverage(False)


def test_entry_split_and_redirect_fields_have_explicit_wire_values():
    entry = Entry(True, 0b110, 1, 0x12, 3, True, True, 1)
    values = encode(Beat(
        entries=(entry,) + (Entry(),) * 7,
        split_done=SplitDone(True, 4),
        redirect=Redirect(True, 1, 0, 0x155),
    ))
    assert values['in_entries_0_static_uopType'] == 6
    assert values['in_entries_0_static_robIdx_flag'] == 1
    assert values['in_entries_0_static_robIdx_value'] == 0x12
    assert values['in_entries_0_dynamic_exception'] == 1
    assert values['in_splitDoneUpdate_bits_entryIdxOH'] == 0x10
    assert values['in_redirect_bits_level'] == 1
    assert values['in_redirect_bits_robIdx_value'] == 0x155
