"""The fixed ABI is not inferred from the same possibly damaged live schema."""
import pytest
from suites.frontend.bpu.testbenches.mbtb.env.bundle.abi import expected_schema
from suites.frontend.bpu.testbenches.mbtb.env.bundle.abi import validate_schema


def test_complete_default_config_schema_and_channel_specific_address_widths():
    schema=expected_schema();validate_schema(schema)
    assert schema['lookup.start_pc']==schema['prediction.entries[9].bits.target_addr']==50
    assert schema['training.start_pc0']==schema['training.branches[7].target']==49
    assert 'prediction.meta_entries[1][4].rawHit' in schema
    assert 'prediction.meta_entries[1][4].attribute.branchType' not in schema
    assert schema['training.meta_entries[1][4].rawHit']==1
    assert schema['training.meta_entries[1][4].position']==5
    assert 'training.meta_entries[1][4].counter_value' not in schema


@pytest.mark.parametrize('fault',('missing','extra','width','two-ways','victim-attribute','training-victim'))
def test_matching_but_non_default_geometry_or_a_fabricated_dce_leaf_is_rejected(fault):
    schema=expected_schema()
    if fault=='missing':schema.pop('lookup.s2_fire')
    elif fault=='extra':schema['lookup.unknown']=1
    elif fault=='width':schema['lookup.start_pc']=49
    elif fault=='two-ways':schema={name:width for name,width in schema.items() if 'meta_entries[0][3]' not in name}
    elif fault=='victim-attribute':schema['prediction.meta_entries[1][4].attribute.branchType']=2
    else:schema['training.meta_entries[1][4].counter_value']=2
    with pytest.raises(ValueError,match='DefaultConfig ABI differs'):validate_schema(schema)
