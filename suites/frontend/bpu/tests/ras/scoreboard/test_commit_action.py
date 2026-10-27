"""Human stack meaning and actual receipt ownership discriminators."""
from copy import deepcopy
import pytest
from bpuverify.ras.model.commit_action import Program,A,B,C,RULES
from bpuverify.ras.monitor.commit_action import receipts
from bpuverify.ras.coverage.commit_action import Coverage



@pytest.mark.parametrize('action,expected',((1,(A,)),(2,(A,B,C)),(3,(A,C))))
def test_resolved_action_changes_only_its_youngest_logical_frame(action,expected):
    assert Program(action).stack==expected


@pytest.mark.parametrize('invalid',(0,4,True,None,1.0))
def test_invalid_or_ambiguous_actions_are_not_silently_reinterpreted(invalid):
    with pytest.raises(ValueError):Program(invalid)


def source_rows():
    meta=dict(ssp=2,tosw=dict(flag=0,value=2))
    return [dict(commit=dict(valid=1,bits=dict(action=3,meta=deepcopy(meta))),
        pending_commit=dict(valid=0)),
        dict(commit=dict(valid=0),pending_commit=dict(valid=1,push=0,pop=0,**meta))]


def test_acceptance_without_any_child_operation_is_still_a_real_receipt_not_a_PASS():
    payload,registered=receipts(source_rows())
    assert payload['action']==3 and not registered['push'] and not registered['pop']
    assert Program(3).stack==(A,C)


@pytest.mark.parametrize('fault',('missing-input','missing-registered','duplicate-input','duplicate-registered','wrong-source'))
def test_receipt_count_or_source_mismatch_cannot_be_normalized_away(fault):
    rows=source_rows()
    if fault=='missing-input':rows[0]['commit']['valid']=0
    elif fault=='missing-registered':rows[1]['pending_commit']['valid']=0
    elif fault=='duplicate-input':rows.append(deepcopy(rows[0]))
    elif fault=='duplicate-registered':rows.append(deepcopy(rows[1]))
    else:rows[1]['pending_commit']['ssp']=1
    with pytest.raises(AssertionError):receipts(rows)


@pytest.mark.parametrize('action',(1,2,3))
@pytest.mark.parametrize('missing',RULES)
def test_missing_transport_effect_or_consumer_proof_cannot_receive_checked_credit(action,missing):
    coverage=Coverage(Program(action))
    for rule in RULES:
        if rule!=missing:coverage.reach(rule)
    with pytest.raises(AssertionError):coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('action',(1,2,3))
def test_complete_case_only_checks_its_own_semantic_mode(action):
    coverage=Coverage(Program(action))
    for rule in RULES:coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage==pytest.approx(100/3)
    with pytest.raises(AssertionError):coverage.finish()



def complete_rows():
    source,registered=source_rows()
    result=[]
    for tick,row in ((10,source),(11,registered),(12,dict(commit=dict(valid=0),pending_commit=dict(valid=0)))):
        result.append(dict(tick=tick,head=2,cells=[dict(address=A//2,counter=0),
            dict(address=B//2,counter=0),dict(address=C//2,counter=0)],**deepcopy(row)))
    return result


def test_default_commit_summary_keeps_actual_event_ticks_and_state_without_cycle_rows():
    from bpuverify.ras.monitor.commit_action import commit_facts
    rows=complete_rows();before=deepcopy(rows);facts=commit_facts(rows)
    assert set(facts)=={'actual_input','actual_registered','input_tick','registered_tick','retained'}
    assert facts['input_tick']==10 and facts['registered_tick']==11
    assert facts['actual_input']==rows[0]['commit']['bits']
    assert facts['actual_registered']==rows[1]['pending_commit']
    assert facts['retained']==dict(head=2,cells=rows[-1]['cells'])
    facts['actual_input']['meta']['ssp']=0;facts['retained']['cells'][0]['counter']=7
    assert rows==before


def test_compact_summary_still_rejects_missing_real_registered_receipt():
    from bpuverify.ras.monitor.commit_action import commit_facts
    rows=complete_rows();rows[1]['pending_commit']['valid']=0
    with pytest.raises(AssertionError):commit_facts(rows)


def test_default_trace_export_does_no_serialization_or_filesystem_work(tmp_path):
    from bpuverify.ras.env.commit_action import export_commit_trace
    from bpuverify.common.env.trace import trace_exports
    class NotSerializable:
        def __iter__(self):raise AssertionError('disabled diagnostics touched raw rows')
    target=tmp_path/'not-created'/'cycles.json'
    with trace_exports(False):assert export_commit_trace(NotSerializable(),target) is None
    assert not target.parent.exists()


def test_explicit_trace_keeps_the_exact_original_rows_in_compressed_output(tmp_path):
    import gzip
    import json
    from bpuverify.ras.env.commit_action import export_commit_trace
    from bpuverify.common.env.trace import trace_exports
    rows=complete_rows();before=deepcopy(rows)
    with trace_exports(True):target=export_commit_trace(rows,tmp_path/'cycles.json')
    assert target.suffix=='.gz'
    with gzip.open(target,'rt') as stream:assert json.load(stream)==rows
    assert rows==before


def test_optional_trace_error_cannot_replace_original_semantic_mismatch(monkeypatch,tmp_path):
    import bpuverify.ras.env.commit_action as env
    from bpuverify.ras.checker.commit_action import CommitActionChecks
    from toffee import ScoreboardMismatch
    checker=CommitActionChecks(Program(3))
    with pytest.raises(ScoreboardMismatch) as raised:checker.check(C,B,'retained original caller')
    original=raised.value
    def broken(*args,**kwargs):raise OSError('diagnostic storage unavailable')
    monkeypatch.setattr(env,'dump_trace',broken)
    assert env.export_commit_trace(complete_rows(),tmp_path/'cycles.json',primary=original) is None
    assert checker.board.status.first_failure is original
    assert 'retained original caller' in str(original)
    assert 'diagnostic storage unavailable' in original.__notes__[-1]


def test_requested_trace_error_is_not_silently_lost_without_a_primary_failure(monkeypatch,tmp_path):
    import bpuverify.ras.env.commit_action as env
    def broken(*args,**kwargs):raise OSError('diagnostic storage unavailable')
    monkeypatch.setattr(env,'dump_trace',broken)
    with pytest.raises(OSError,match='storage unavailable'):
        env.export_commit_trace(complete_rows(),tmp_path/'cycles.json')
