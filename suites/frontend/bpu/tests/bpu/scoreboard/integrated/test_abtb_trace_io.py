import gzip
import json
import pytest
from suites.frontend.bpu.bpu.case.abtb.trace_io import read_trace
from suites.frontend.bpu.bpu.case.abtb.trace_io import write_trace


@pytest.mark.parametrize('value',[None,{},[],dict(frames=[dict(tick=1,phase='preedge',value=[0]*1024)],
    pending=None,flag=True,tuple_data=(1,2),unicode='完整轨迹')])
def test_compressed_trace_is_byte_exact_original_json(tmp_path,value):
    path=tmp_path/'trace.json.gz'
    write_trace(path,value)
    encoded=(json.dumps(value)+'\n').encode('utf-8')
    with gzip.open(path,'rb') as stream:assert stream.read()==encoded
    assert read_trace(path)==json.loads(encoded)


def test_existing_evidence_is_never_overwritten(tmp_path):
    path=tmp_path/'trace.json.gz'
    write_trace(path,dict(first=1))
    before=path.read_bytes()
    with pytest.raises(FileExistsError):write_trace(path,dict(second=2))
    assert path.read_bytes()==before


def test_unserializable_value_cannot_create_partial_evidence(tmp_path):
    path=tmp_path/'trace.json.gz'
    with pytest.raises(TypeError):write_trace(path,object())
    assert not path.exists()


@pytest.mark.parametrize('fault',['truncated','crc'])
def test_corrupted_trace_is_not_a_successful_read(tmp_path,fault):
    path=tmp_path/'trace.json.gz'
    write_trace(path,dict(frames=[dict(tick=1,value=[1]*1024)]))
    content=path.read_bytes()
    bad=content[:-5] if fault=='truncated' else content[:-8]+bytes([content[-8]^1])+content[-7:]
    broken=tmp_path/'bad.json.gz'
    broken.write_bytes(bad)
    with pytest.raises((EOFError,gzip.BadGzipFile)):read_trace(broken)
