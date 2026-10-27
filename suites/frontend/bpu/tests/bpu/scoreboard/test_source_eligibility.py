"""Cancellation, failure and reset are distinct semantic dispositions."""
import ast
from pathlib import Path
import pytest
from bpuverify.bpu.model.source_eligibility import Program,MODES,FATAL


@pytest.mark.parametrize('mode',MODES)
def test_declared_disposition_matches_public_driver_failure_and_cancellation_contract(mode):
    program=Program(mode)
    assert program.terminal_driver==(mode in FATAL)
    assert program.accepts==(0 if mode in FATAL else 2 if mode=='valid-old-late' else 1)
    assert program.reset==mode.startswith('reset-')
    assert program.state()['environment_contract_only']
    assert not program.state()['full_FTQ_reachability_proved']


@pytest.mark.parametrize('invalid',(None,True,1,'not-a-source-event'))
def test_ambiguous_modes_are_rejected_without_any_native_work(invalid):
    with pytest.raises(ValueError):Program(invalid)


def test_program_has_no_clock_SDK_driver_or_predictor_state_dependency():
    path=Path(__file__).resolve().parents[3]/'bpuverify/bpu/model/source_eligibility.py'
    tree=ast.parse(path.read_text())
    assert {n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}=={'dataclasses'}
    assert not any(isinstance(n,ast.Import) for n in ast.walk(tree))
