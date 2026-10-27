"""Static geometry binds complete entry and masked counter channels separately."""
from types import SimpleNamespace as NS
from bpuverify.bpu.bundle import main_service as module
from bpuverify.bpu.bundle.values import _plain


class Signal:
    def __init__(self,value=0):self.value=value


def test_main_geometry_is_not_disguised_as_a_history_table_and_all_payloads_are_immutable(monkeypatch):
    signals={}
    def signal(dut,name):return signals.setdefault(name,Signal())
    monkeypatch.setattr(module,'memory_signal_names',lambda dut:('TOP.unit.mbtb.io_enable',))
    monkeypatch.setattr(module,'memory_signal',signal)
    binding,ports=module.main_service_binding(NS(dut=NS(clock=object())),alignment=0,bank=0)
    sampler=binding.bits.compile_sampler();before=_plain(sampler())
    assert len(ports)==3
    assert set(before['writes'][0]['bits'])=={'row','tag','position','kind','action','carry','offset'}
    assert set(before['writes'][2]['bits'])=={'row','mask','counters'}
    base='unit.mbtb.alignBanks_0.internalBanks_0.'
    signals[base+'entryWriteBuffer.io_read_1_bits_entry_targetLowerBits'].value=0x1200
    signals[base+'counterWriteBuffer.io_deq_bits_counters_0_value'].value=3
    after=_plain(sampler())
    assert before['writes'][1]['bits']['offset']==0 and after['writes'][1]['bits']['offset']==0x1200
    assert before['writes'][2]['bits']['counters']==(0,0) and after['writes'][2]['bits']['counters']==(3,0)
    assert not any('tables_' in name or '__Vdly' in name for name in signals)


def test_SC_training_read_observation_has_independent_valid_index_and_bank():
    from bpuverify.bpu.bundle.statistical import statistical_bundle,TABLES
    signals={}
    def signal(name):return signals.setdefault(name,Signal())
    sampler=statistical_bundle(signal).compile_sampler()
    before=_plain(sampler())
    assert len(before['reads'])==5 and len(before['updates'])==5
    signals['sc.pathTable_0.io_trainReadReq_valid'].value=1
    signals['sc.pathTable_0.io_trainReadReq_bits_setIdx'].value=69
    signals['sc.pathTable_0.io_trainReadReq_bits_bankMask'].value=1
    after=_plain(sampler())
    assert before['reads'][0]==dict(valid=0,index=0,bank=0)
    assert after['reads'][0]==dict(valid=1,index=69,bank=1)
    assert not any(port['valid'] for port in after['updates'])


def test_SC_full_numeric_reads_and_consumed_evidence_have_separate_immutable_snapshots():
    from bpuverify.bpu.bundle.statistical import statistical_bundle
    signals={}
    def signal(name):return signals.setdefault(name,Signal())
    sample=statistical_bundle(signal).compile_sampler()
    before=_plain(sample())
    assert tuple(map(len,before['prediction_read']['words']))==(4,4,4,4,16)
    assert tuple(map(len,before['prediction_evidence']['words']))==(4,4,4,4,16)
    signals['sc.globalTable_0.io_predictReadResp_0_ctr_value'].value=63
    signals['sc.s1_globalIdx_0'].value=17
    signals['sc.s1_commonHRValid'].value=1
    signals['sc.globalTable_0.predictReadBankMaskNext'].value=2
    signals['sc.s2_globalPercsum_r'].value=127
    signals['sc.s2_globalIdx_0'].value=17
    after=_plain(sample())
    assert before['prediction_read']['words'][1][0]==0
    assert after['prediction_read']['words'][1][0]==63
    assert after['prediction_read']['indices'][1]==17 and after['prediction_read']['history_valid']==1
    assert after['prediction_read']['banks'][1]==2
    assert after['prediction_evidence']['words'][1][0]==127
    assert after['prediction_evidence']['indices'][1]==17
    assert not any('__Vdly' in name for name in signals)


def test_main_learning_receipts_preserve_independent_expected_and_actual_values():
    from copy import deepcopy
    import pickle
    from bpuverify.bpu.monitor.service import MainLearningReceipts
    from tests.bpu.scoreboard.test_ahead_direction_proposals import main_model
    main=main_model(hit=True,counter=0,taken=False,correction=False)
    receipts=MainLearningReceipts(NS(model=NS(sources=NS(main=main)),raise_failure=lambda:None))
    row=dict(direction=dict(valid=1,ready=1,bits=dict(row=0,mask=2,counters=(0,2))),
        incoming=(dict(valid=0),dict(valid=0)))
    before=pickle.dumps(main)
    receipts.capture_state(NS(tick=10),row)
    row['direction']['bits']['counters']=(0,0)
    result=receipts.state()
    assert result['offers'][0]['expected']['values']==(None,0)
    assert result['offers'][0]['direction']['bits']['counters']==(0,2)
    assert pickle.dumps(main)==before and not result['truncated']
    result['offers'].clear()
    assert len(receipts.state()['offers'])==1


def test_main_learning_receipts_bound_events_and_disclose_truncation():
    from bpuverify.bpu.monitor.service import MainLearningReceipts
    from bpuverify.mbtb.model.semantic import MbtbReference
    receipts=MainLearningReceipts(NS(model=NS(sources=NS(main=MbtbReference())),raise_failure=lambda:None),capacity=2)
    for tick in range(3):
        receipts.capture_state(NS(tick=tick),dict(direction=dict(valid=1),incoming=(dict(valid=0),dict(valid=0))))
        receipts.write_accepted(2,NS(accepted_tick=tick,value=dict(row=tick)))
    state=receipts.state()
    assert state['offers_seen']==state['services_seen']==3
    assert len(state['offers'])==len(state['services'])==2 and state['truncated']
    assert [row['tick'] for row in state['offers']]==[1,2]
