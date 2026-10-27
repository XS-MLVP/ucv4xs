"""Static read-only MicroTAGE IO and the parent's original S3 metadata."""
from toffee import Bundle


FIELDS=(('valid','valid'),('base','baseTaken'),('strong','baseIsStrongBias'),
    ('hit','hit'),('predicted','predTaken'),('provider','tableId'),
    ('position','cfiPosition'),('counter','takenCtr_value'))


def early_direction_bundle(signal):
    def maintenance_table(table):
        prefix=f'utage.MicroTageTable{"" if table==0 else "_1"}.wbuffer.'
        return Bundle(age=signal(prefix+'io_usefulReset'),
            allocate=signal(prefix+'io_train_t1_alloc_valid'),
            update=signal(prefix+'io_train_t1_update_valid'))
    def metadata(base):
        return Bundle(entries=tuple(Bundle(**{key:signal(f'{base}abtbResult_{way}_{field}')
            for key,field in FIELDS}) for way in range(4)),
            indices=tuple(signal(f'{base}readIndex_{table}') for table in range(2)),
            history=tuple(signal(f'{base}foldedPathHistForTrain_hist_{index}_foldedHist') for index in range(19)))
    return Bundle(meta=metadata('utage.io_meta_bits_'),
        maintenance=Bundle(low=signal('utage.lowTickCounter'),fire=signal('utage.t1_fire'),
            need=signal('utage.t1_needAlloc'),mask=signal('utage.t1_normalAllocMask'),
            tables=tuple(maintenance_table(table) for table in range(2))),
        read_tags=tuple(signal(f'utage.a2_predRead_{table}_tag') for table in range(2)),
        useful=tuple(tuple(signal(f'utage.MicroTageTable{"" if table==0 else "_1"}.wbuffer.'
            f'usefulEntries_{index%4}_{index//4}_value') for index in range(512)) for table in range(2)),
        hits=tuple(signal(f'utage.io_prediction_hitVec_{way}') for way in range(4)),
        taken=tuple(signal(f'utage.io_prediction_takenVec_{way}') for way in range(4)),
        fast=Bundle(valid=signal('utage.io_fastTrain_valid'),meta=metadata('s3_utageMeta_'),**{
            key:signal('utage.io_fastTrain_bits_'+field) for key,field in (
                ('pc','startPc_addr'),('position','branch_cfiPosition'),
                ('taken','branch_taken'),('kind','branch_attribute_branchType'))}))
