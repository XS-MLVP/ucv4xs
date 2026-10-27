#!/usr/bin/env python3
"""In-memory corrupted input/effect + matching expected must still be rejected."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import traceback

from audit_lsq_joint_history_v3 import JointAudit
from audit_lsq_population_v1 import events, paths_by_node
from audit_sq_initial import ROOT, sha


def check(rows):
    audit = JointAudit()
    for row in rows:
        audit.step(row)
    return audit.finish()


def audit(name):
    assert name in ("lsq-joint-capacity-04","lsq-expanded-16")
    run = ROOT/"results"/name
    paths = paths_by_node(run)
    positive = next(p for n,p in sorted(paths.items()) if "test_joint_capacity.py::" in n and "[none-29200]" in n)
    redirect = next(p for n,p in sorted(paths.items()) if "test_joint_capacity.py::" in n and "[redirect-29200]" in n)
    sources = {str(p.relative_to(run)):sha(p) for p in (positive,redirect)}
    base = {p:list(events(p)) for p in (positive,redirect)}
    for rows in base.values():
        check(rows)
    results = []

    def reject(label,path,index,mutate):
        rows = list(base[path])
        row = rows[index] = copy.deepcopy(rows[index])
        changed = mutate(row)
        assert changed
        try:
            check(rows)
        except AssertionError as exc:
            location = traceback.extract_tb(exc.__traceback__)[-1]
            assert location.filename.endswith("audit_lsq_joint_history_v3.py"), "not an independent semantic rejection"
            results.append(dict(case=label,source=str(path.relative_to(run)),mutated_tick=row["post_tick"],changes=changed,
                                in_memory_only=True,rejected=True,semantic_location=f"{Path(location.filename).name}:{location.lineno}",reason=str(exc)))
        else:
            raise AssertionError(("corrupted original obligation was accepted",label))

    rows = base[positive]
    index,lane = next((n,lane) for n,row in enumerate(rows) for lane,q in enumerate(row["input"]["loads"]) if q["execution"]["valid"] and q["execution"]["replay_feedback"])

    def wrong_slot(row):
        q = row["input"]["loads"][lane]["execution"]
        old = q["slot"]
        q["slot"] = (old+3) % 120  # Same bank, different original slot.
        pins = [k for k in row["pins"] if k.startswith(f"io_ldu_ldin_{lane}_") and k.endswith("_replayQueueIdx")]
        assert len(pins)==1
        row["pins"][pins[0]]=row["post_pins"][pins[0]]=q["slot"]
        return [dict(field="input_and_both_raw_pins_original_slot",old=old,new=q["slot"],expected_outputs_unchanged=True)]
    reject("same_bank_wrong_original_replay_feedback_slot",positive,index,wrong_slot)

    index = next(n for n,r in enumerate(rows) if r["before"]["io_cmoOpReq_valid"] and r["input"]["cache_ready"])

    def wrong_opcode(row):
        pin = "io_cmoOpReq_bits_opcode"
        old = row["before"][pin]
        row["before"][pin]=row["expected_before"][pin]=old ^ 1
        return [dict(field=pin,old=old,new=old ^ 1,matching_expected_also_polluted=True)]
    reject("original_CBO_opcode_even_with_matching_expected",positive,index,wrong_opcode)

    index,lane = next((n,lane) for n,r in enumerate(rows) for lane in range(2) if r["before"][f"io_sbuffer_req_{lane}_valid"] and r["input"]["sbuffer_ready"][lane] and r["before"][f"io_sbuffer_req_{lane}_bits_wline"])

    def wrong_zero(row):
        pin = f"io_sbuffer_req_{lane}_bits_data"
        old = row["before"][pin]
        row["before"][pin]=row["expected_before"][pin]=old ^ 1
        return [dict(field=pin,old=old,new=old ^ 1,matching_expected_also_polluted=True)]
    reject("actual_original_zero_byte_even_with_matching_expected",positive,index,wrong_zero)

    rr = base[redirect]
    cut = next(n for n,r in enumerate(rr) if r["input"]["redirect"]["valid"])
    index = next(n for n,r in enumerate(rr) if n>cut and r["input"]["bus"]["response"])

    def missing_cancelled_response(row):
        row["input"]["bus"]["response"]=False
        row["pins"]["io_uncache_resp_valid"]=row["post_pins"]["io_uncache_resp_valid"]=0
        return [dict(field="input_and_raw_resp_valid",old=True,new=False,matching_expected_retained_as_original_actual=True,
                     obligation="a cancelled original accepted request still owes its real response; no redirect waiver")]
    reject("cancel_cannot_erase_one_unreturned_original_external_job",redirect,index,missing_cancelled_response)
    assert len(results)==4 and sources=={str(p.relative_to(run)):sha(p) for p in (positive,redirect)}
    dest = run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    file = Path(__file__)
    target = dest/file.name
    if target.exists():
        assert sha(file)==sha(target)
    else:
        shutil.copy2(file,target)
    report = dict(run=name,status="four_original_obligation_mutants_rejected_without_altering_evidence",original_journals_sha256=sources,
                  mutations=results,auditor_sha256=sha(target),semantic_auditor_sha256=sha(ROOT/"tools/audit_lsq_joint_history_v3.py"),
                  limits="Only in-memory copies. Actual pre effect + matching expected are co-polluted for CBO/zero; Replay feedback and missing cancelled response mutate input and both raw pin maps. Standard checked/masks remain green, yet independent original-UID semantics reject. Original source journals/checks/results/RTL unchanged. This is audit sensitivity, not DUT functionality, new coverage or complete random acceptance.")
    out = run/"joint-negative-audit-v1.json"
    if out.exists():
        assert json.loads(out.read_text())==report
    else:
        out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
