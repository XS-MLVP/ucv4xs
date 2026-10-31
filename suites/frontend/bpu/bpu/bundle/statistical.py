"""Read-only SC/CommonHR projections; every field uses public memory-direct SDK."""
from suites.frontend.bpu.models.configuration import *

from toffee import Bundle

TABLES = ('pathTable_0', 'pathTable_1', 'globalTable_0', 'globalTable_1', 'bwTable_0', 'bwTable_1', 'imliTable', 'biasTable')
META_VECTORS = ('scBiasLowerBits', 'scPred', 'useScPred', 'sumAboveThres',
                'tageCtr', 'tagePred', 'tagePredValid')
DEBUG_VECTORS = ('scPathTakenVec', 'scGlobalTakenVec', 'scBWTakenVec',
                 'scImliTakenVec', 'scBiasTakenVec')
INDEX_FIELDS=('pathIdx_0','pathIdx_1','globalIdx_0','globalIdx_1','bwIdx_0','bwIdx_1','imliIdx','biasIdx')
EVIDENCE_FIELDS=('pathPercsum','globalPercsum','bwPercsum','imliPercsum','biasPercsum')


def metadata_bundle(signal, base):
    return Bundle(**{field: tuple(signal(f'{base}{field}_{slot}') for slot in range(RESULT_SLOTS))
        for field in META_VECTORS}, debug=Bundle(
        **{field: tuple(signal(f'{base}debug_{field}_{slot}') for slot in range(RESULT_SLOTS))
            for field in DEBUG_VECTORS},
        **{field: tuple(signal(f'{base}debug_{field}_{table}') for table in range(2))
            for field in ('predPathIdx', 'predGlobalIdx', 'predBWIdx')},
        **{field: signal(f'{base}debug_{field}') for field in ('predImliIdx', 'predBiasIdx')}))


def history_bundle(signal, base, *, loop=True):
    return Bundle(**{field: signal(base + field) for field in ('valid', 'ghr', 'bw')},
        **(dict(imli=signal(base + 'imli')) if loop else {}))


def statistical_bundle(signal):
    def training_read(table):
        base = f'sc.{table}.io_trainReadReq_'
        return Bundle(valid=signal(base+'valid'),index=signal(base+'bits_setIdx'),bank=signal(base+'bits_bankMask'))
    def update(table):
        base = f'sc.{table}.io_update_'
        size = 4 * SC_WAYS if table == 'biasTable' else SC_WAYS
        return Bundle(valid=signal(base + 'valid'), index=signal(base + 'setIdx'),
            bank=signal(base + 'bankMask'), mask=tuple(signal(base + f'wayMask_{i}') for i in range(size)),
            data=tuple(signal(base + f'entryVec_{i}_ctr_value') for i in range(size)))
    def weights(table):
        return tuple(signal(f'sc.{table}.io_predictReadResp_{i}_ctr_value')
            for i in range(4 * SC_WAYS if table=='biasTable' else SC_WAYS))
    def evidence(field):
        return tuple(signal('sc.s2_'+field+'_r'+('' if i==0 else '_'+str(i)))
            for i in range(4 * SC_WAYS if field=='biasPercsum' else SC_WAYS))
    return Bundle(ready=signal('sc.io_trainReady'),
        state=history_bundle(signal, 'commonHR.commonHR_', loop=False),
        lookup=history_bundle(signal, 'commonHR.io_s0_commonHR_', loop=False),
        loop_state=signal('commonHR.imli'), loop_lookup=signal('commonHR.io_s0_imli'),
        thresholds=tuple(signal(f'sc.scThreshold_{slot}_value') for slot in range(SC_WAYS)),
        prediction_requests=tuple(signal(f'sc.{table}.io_predictReadReq_valid') for table in TABLES),
        prediction_read=Bundle(indices=tuple(signal('sc.s1_'+field) for field in INDEX_FIELDS),
            history_valid=signal('sc.s1_commonHRValid'),
            banks=tuple(signal(f'sc.{table}.predictReadBankMaskNext') for table in TABLES),
            words=tuple(weights(table) for table in TABLES)),
        prediction_evidence=Bundle(indices=tuple(signal('sc.s2_'+field) for field in INDEX_FIELDS),
            words=tuple(evidence(field) for field in EVIDENCE_FIELDS)),
        prediction_composition=Bundle(
            history_sums=tuple(signal(f'sc.s2_sumPercsum_{way}') for way in range(SC_WAYS)),
            candidates=tuple(tuple(signal(f'sc.s2_totalPercsumAll_{way}_{bias}')
                for bias in range(4)) for way in range(SC_WAYS)),
            selected=tuple(signal(f'sc.s2_totalPercsum_{slot}') for slot in range(RESULT_SLOTS))),
        reads=tuple(training_read(table) for table in TABLES),
        updates=tuple(update(table) for table in TABLES))
