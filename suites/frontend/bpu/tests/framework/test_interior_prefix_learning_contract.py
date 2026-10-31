"""Human execution-prefix obligations precede native stimulus."""
import ast
import json
from pathlib import Path
from suites.frontend.bpu.bpu.coverage.interior_prefix_learning import RULES
from suites.frontend.bpu.bpu.model.tage.interior_prefix_learning import PROGRAMS


def test_interior_prefix_requirement_is_behavior_not_physical_coordinate():
    c=json.loads(Path('docs/interior-prefix-learning-contract.json').read_text())
    assert c['features']==['BPU-INT-086'] and c['new_feature_IDs']==0
    assert '实际执行' in c['owner'] and '固定延时' in c['schedule']
    assert len(PROGRAMS)==4 and len(RULES)==17 and c['gap_basis']['open_rows']==103


def test_native_case_hides_edges_raw_IO_and_task_join_details():
    text=Path('tests/bpu/testcase/test_interior_prefix_learning.py').read_text()
    assert not any(word in text for word in ('FallingEdge','RisingEdge','ClockCycles','asyncio.gather','get_','set_','.Set('))
    tree=ast.parse(Path('bpu/model/tage/interior_prefix_learning.py').read_text())
    assert {node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}=={
        'dataclasses','suites.frontend.bpu.bpu.model.tage.direction_turnaround','suites.frontend.bpu.bpu.model.tage.dual_migration'}


def test_all_source_supported_semantic_references_exist():
    c=json.loads(Path('docs/interior-prefix-learning-contract.json').read_text())
    for reference in c['source_chain']:
        file,line=reference.rsplit(':',1);assert 0<int(line)<=len(Path(file).read_text().splitlines())
