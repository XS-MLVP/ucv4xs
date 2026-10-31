"""Read-only memory-direct predictor IO; no table contents enter the oracle."""
from toffee import Bundle


def ahead_bundle(parent_signal):
    signal=lambda field:parent_signal('abtb.'+field)
    def meta(base):
        return Bundle(valid=signal(base+'_valid'),row=signal(base+'_setIdx'),banks=signal(base+'_bankMask'),
            entries=tuple(Bundle(**{key:signal(f'{base}_entries_{way}_'+field) for key,field in (
                ('hit','hit'),('position','position'),('kind','attribute_branchType'),
                ('action','attribute_rasAction'),('target_low','targetLowerBits'))}) for way in range(4)))
    predictions=tuple(Bundle(valid=signal(f'io_result_entries_{way}_valid'),**{
        key:signal(f'io_result_entries_{way}_bits_'+field) for key,field in (
            ('taken','taken'),('target','target_addr'),('position','cfiPosition'),
            ('kind','attribute_branchType'),('action','attribute_rasAction'))}) for way in range(4))
    micro=tuple(Bundle(valid=signal(f'io_toMicroTage_result_{way}_valid'),**{
        key:signal(f'io_toMicroTage_result_{way}_bits_'+field) for key,field in (
            ('taken','taken'),('kind','attribute_branchType'),('strong','isStrongBias'))}) for way in range(4))
    fast=Bundle(valid=signal('io_fastTrain_valid'),meta=meta('io_fastTrain_bits_abtbMeta'),**{
        key:signal('io_fastTrain_bits_'+field) for key,field in (
            ('pc','startPc_addr'),('target','branch_target_addr'),('taken','branch_taken'),
            ('position','branch_cfiPosition'),('kind','branch_attribute_branchType'),('action','branch_attribute_rasAction'))})
    return Bundle(meta=meta('io_meta'),entries=predictions,micro=micro,fast=fast)
