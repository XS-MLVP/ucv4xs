"""Direction-recovery requirements are distinct from steady four-way residency."""
from pathlib import Path
from tempfile import mkdtemp

from bpuverify.bpu.model.abtb.final_not_taken import plan
from bpuverify.bpu.case.abtb.final_not_taken import run_final_not_taken_cycle
from bpuverify.bpu.coverage.abtb.supplemental import CounterCoverage
from bpuverify.bpu.coverage.bypass.supplemental import IntegratedCoverage
from bpuverify.bpu.coverage.bypass.selection import ResponseSelectionCoverage


async def check_direction_recovery_case(agent, output, *, bank, entry_set, table, slot):
    plan(bank, entry_set)  # Reject unsupported scope before creating artifacts/stimulus.
    if type(table) is not int or table not in range(2) or type(slot) is not int or slot not in range(8):
        raise ValueError('fixed MicroTAGE table0/1 and shadow slot0..7 required')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    case = f'direction-recovery-bank{bank}-set{entry_set}-table{table}-slot{slot}'
    artifact = Path(mkdtemp(prefix=case + '-', dir=output))
    trace = await run_final_not_taken_cycle(agent, artifact, bank=bank, entry_set=entry_set,
                                           direction_preparation='redirect')
    bypass, counter, selection = IntegratedCoverage(), CounterCoverage(), ResponseSelectionCoverage()
    bypass_summary = bypass.collect(trace)
    counter_summary = counter.collect(trace)
    selection_summary = selection.collect(trace, required=((table, slot, 'fallback'),))
    # No collector is exported until every full replay and the fallback gate pass.
    bypass.save(output, case=case)
    counter.save(output, case=case)
    selection.save(output, case=case)
    return dict(case=case, artifact=str(artifact), bypass=bypass_summary,
        counter=counter_summary, selection=selection_summary,
        steady_four_way_residency_claimed=False, full_matrix_or_FTQ_closed=False)
