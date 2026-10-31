"""Synthetic observations must not manufacture native service credit."""
from copy import deepcopy
from types import SimpleNamespace
import pytest

from suites.frontend.bpu.utage.model.persistence import PersistenceLedger, Version
from suites.frontend.bpu.utage.monitor.learning_persistence import Monitor


def observed_service():
    version=Version(10,(1,19,54,6),5,'reward')
    ledger=PersistenceLedger();ledger.source(version,dict(original=10));ledger.accept(dict(original=10),12)
    ledger.publish(*version.identity[:2],version.entry,14)
    monitor=Monitor.__new__(Monitor)
    monitor.ledger=ledger;monitor.failure=None;monitor.previous_enq=(0,0)
    monitor.public=lambda:dict(valid=0,bits=None)
    monitor.shadow=tuple(SimpleNamespace(sample_at=lambda event:SimpleNamespace(value=dict(enq=0,cells=()))) for _ in (0,1))
    services=[dict(valid=0,success=0,index=0,data={}),dict(valid=1,success=1,index=19,data=version.entry)]
    monitor.launched_service=(15,services)
    monitor.attempts=[];monitor.storage_checks=[];monitor.memory_changes=[]
    memory={(1,19):version.entry}
    monitor.memory=lambda:deepcopy(memory)
    monitor.last_memory={(1,19):dict(version.entry,counter=4)}
    return monitor,ledger,version,services,memory


def test_actual_service_and_array_content_jointly_establish_persistence():
    monitor,ledger,version,services,memory=observed_service()
    monitor.after(SimpleNamespace(tick=16));monitor.check()
    ledger.finish_phase([version.owner],persistent=True)
    assert len(monitor.storage_checks)==len(monitor.memory_changes)==len(ledger.services)==1


@pytest.mark.parametrize('fault',('no-success','invalid-request'))
def test_request_or_array_value_alone_is_not_actual_service(fault):
    monitor,ledger,version,services,memory=observed_service()
    services[1]['success' if fault=='no-success' else 'valid']=0
    monitor.last_memory=deepcopy(memory)
    monitor.after(SimpleNamespace(tick=16));monitor.check()
    assert not ledger.services
    with pytest.raises(AssertionError,match='not actually persistent'):ledger.finish_phase([version.owner],persistent=True)


@pytest.mark.parametrize('field',('valid','tag','position','counter'))
def test_successful_request_cannot_hide_wrong_actual_storage(field):
    monitor,ledger,version,services,memory=observed_service()
    memory[1,19][field]^=1
    monitor.after(SimpleNamespace(tick=16))
    with pytest.raises(AssertionError,match='service/storage differ'):monitor.check()
    assert not ledger.services


def test_changed_neighbor_without_service_is_rejected():
    monitor,ledger,version,services,memory=observed_service()
    other=(0,3);monitor.last_memory[other]=dict(valid=0,tag=0,position=0,counter=0)
    memory[other]=dict(valid=1,tag=5,position=5,counter=7)
    monitor.after(SimpleNamespace(tick=16))
    with pytest.raises(AssertionError,match='changed without its actual service'):monitor.check()


def test_storage_change_without_write_acknowledgement_cannot_be_ignored():
    monitor,ledger,version,services,memory=observed_service();services[1]['success']=0
    monitor.after(SimpleNamespace(tick=16))
    with pytest.raises(AssertionError,match='changed without its actual service'):monitor.check()
    assert not ledger.services


def test_physical_pointer_motion_does_not_prove_a_complete_owned_version():
    monitor,ledger,version,services,memory=observed_service()
    monitor.shadow=(SimpleNamespace(sample_at=lambda event:SimpleNamespace(value=dict(enq=2,cells=(None,)*8))),monitor.shadow[1])
    monitor.after(SimpleNamespace(tick=16))
    with pytest.raises(AssertionError,match='one version write'):monitor.check()


def test_monitor_decodes_native_layout_without_truncating_semantic_tags():
    monitor=Monitor.__new__(Monitor);monitor.layout={1:(8,4,3,1)}
    entry=dict(valid=1,tag=254,position=13,counter=6)
    word=((((1<<8)|254)<<4|13)<<3|6)<<1
    assert monitor.decode(1,word)==entry
    # The native layout adapter does not change the semantic fifteen-bit identity.
    version=Version(10,(1,19,(1<<15)-1,6),5,'reward')
    assert version.entry['tag']==32767
