"""Requirements precede native stimulus and keep semantic-layer boundaries."""
import ast
import json
from pathlib import Path
from bpuverify.utage.model.long_protection import Program,MODES,LIFETIMES,RULES


def test_long_provider_requirement_declares_identity_and_preservation_not_physical_sweep():
    contract=json.loads(Path('docs/utage-long-protection-contract.json').read_text())
    assert contract['new_feature_IDs']==0 and contract['gap_basis']['baseline_zero_rows']==1903
    assert '长提供者' in contract['effect'] and '完整读取' in contract['owner']
    assert len({Program(first,mode,life).label for first in (0,1) for mode in MODES for life in LIFETIMES})==8 and len(RULES)==17


def test_new_native_case_exposes_neither_edges_raw_IO_nor_manual_task_gather():
    source=Path('tests/utage/testcase/test_long_protection.py').read_text()
    assert not any(word in source for word in ('FallingEdge','RisingEdge','ClockCycles','asyncio','get_','set_','.Set('))
    tree=ast.parse(Path('bpuverify/utage/model/long_protection.py').read_text())
    assert not any(isinstance(node,ast.Import) for node in ast.walk(tree))
    assert {node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}=={
        'dataclasses','bpuverify.utage.model.semantic','bpuverify.utage.model.usefulness_events','bpuverify.utage.model.query_identity'}


def test_all_cited_hardware_sources_exist_and_have_the_referenced_line():
    contract=json.loads(Path('docs/utage-long-protection-contract.json').read_text())
    for reference in contract['source_chain']:
        file,line=reference.rsplit(':',1)
        assert 0<int(line)<=len(Path(file).read_text().splitlines())
