"""Opt-in, read-only observation of native exports before managed cleanup.

Load with ``-p suites.memblock.lsq.native_case_probe``. No DUT methods, pin writes,
coverage resets, tool-library edits, or replacement collectors are used.
"""
from suites.memblock.lsq import ROOT as _SUITE_ROOT
from functools import lru_cache
import hashlib
import inspect
import json
from pathlib import Path

import pytest

ROOT = _SUITE_ROOT
KINDS = ("line", "toggle", "branch")
BEFORE = "lsq-progress-regression-15"
AFTER = "store-strict-directory-regression-01"
EXPECTED_TARGET_SHA = "02745152ec8d03a8b3fc0fe1bd36d8db6a3de8adc33705aae55dda486b2bf03d"


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_record(raw):
    if not raw.startswith(b"C '"):
        return None
    marker = raw.rfind(b"' ")
    assert marker > 3
    fields = {}
    for part in raw[3:marker].split(b"\x01"):
        if len(part) >= 2 and part[1:2] == b"\x02":
            fields[part[:1].decode("ascii")] = part[2:].decode("utf-8", "replace")
    return fields, int(raw[marker + 2:])


def point_key(fields):
    return tuple(fields.get(key, "") for key in ("f", "l", "n", "t", "o", "S", "h"))


def digest_keys(keys):
    text = "\n".join(json.dumps(key, ensure_ascii=False, separators=(",", ":")) for key in sorted(keys)) + "\n"
    return hashlib.sha256(text.encode()).hexdigest()


def native(name):
    manifest = json.loads((ROOT / "results" / name / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"]
    matches = [a for a in manifest["artifacts"] if a["kind"] == "native" and a["build"]["name"] == "DUTLsqWrapperDut"]
    assert len(matches) == 1
    row = matches[0]
    assert sha_file(row["path"]) == row["sha256"]
    return row


@lru_cache(maxsize=1)
def targets():
    before, after = native(BEFORE), native(AFTER)
    assert before["build"] == after["build"]
    missing = set()
    with Path(after["path"]).open("rb") as stream:
        for raw in stream:
            parsed = parse_record(raw)
            if parsed is not None:
                point, count = parsed
                if point.get("t") == "toggle" and count == 0 and not point["f"].endswith("_top.sv"):
                    missing.add(point_key(point))
    lost = set()
    with Path(before["path"]).open("rb") as stream:
        for raw in stream:
            parsed = parse_record(raw)
            if parsed is not None:
                point, count = parsed
                key = point_key(point)
                if count > 0 and key in missing:
                    lost.add(key)
    assert len(lost) == 2125 and digest_keys(lost) == EXPECTED_TARGET_SHA
    ordered = tuple(sorted(lost))
    return (dict(before_run=BEFORE, after_run=AFTER, before_dat_SHA256=before["sha256"], after_dat_SHA256=after["sha256"],
                native_build_id=before["build"]["build_id"], target_count=len(ordered), target_set_SHA256=EXPECTED_TARGET_SHA,
                bit_order="sorted original (f,l,n,t,o,S,h) point keys; bit i is target index i; integer encoded as hexadecimal"),
            {key: index for index, key in enumerate(ordered)})


def summarize_export(path):
    origin, index = targets()
    counts = {scope: {kind: dict(hit=0, total=0, count_sum=0) for kind in KINDS}
              for scope in ("raw_all", "original_nonwrapper")}
    seen, hits, target_sum = 0, 0, 0
    digest = hashlib.sha256()
    stat = path.stat()
    with path.open("rb") as stream:
        header = stream.readline()
        assert header == b"# SystemC::Coverage-3\n"
        digest.update(header)
        for raw in stream:
            digest.update(raw)
            parsed = parse_record(raw)
            if parsed is None:
                continue
            point, count = parsed
            kind = point.get("t")
            if kind not in KINDS:
                continue
            for scope in (("raw_all",) if point["f"].endswith("_top.sv") else ("raw_all", "original_nonwrapper")):
                metric = counts[scope][kind]
                metric["total"] += 1
                metric["hit"] += int(count > 0)
                metric["count_sum"] += count
            bit = index.get(point_key(point))
            if bit is not None:
                seen += 1
                target_sum += count
                if count > 0:
                    hits |= 1 << bit
    assert seen == origin["target_count"]
    assert (stat.st_size, stat.st_mtime_ns) == (path.stat().st_size, path.stat().st_mtime_ns)
    return dict(raw_native_dat_SHA256=digest.hexdigest(), raw_native_dat_bytes=stat.st_size,
                metrics=counts, target_hit_count=hits.bit_count(), target_hit_bitmap_hex=hex(hits), target_counter_sum=target_sum)


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_runtest_teardown(item, nextitem):
    yield
    managed = getattr(item.config, "_toffee_managed_coverage", None)
    assert managed is not None and managed.coverage is not None, "native-case probe requires managed X Reactor execution"
    collector = managed.coverage.native
    exports = [row for row in collector.active if row["build"]["name"] == "DUTLsqWrapperDut"]
    if not exports:
        return
    factory = item.funcargs["dut_factory"]
    assert not factory._instances, "read-only probe must run after fixture Finish, not during stimulus"
    origin, _ = targets()
    observed = []
    for row in exports:
        path = Path(row["path"])
        assert path.is_file() and path.stat().st_size > 0
        assert row["build"]["build_id"] == origin["native_build_id"]
        observed.append(dict(native_build_id=row["build"]["build_id"], **summarize_export(path)))
    files = {"observer": Path(__file__), "managed_pytest": Path(inspect.getfile(type(managed))),
             "managed_native_collector": Path(inspect.getfile(type(collector)))}
    report = dict(format="lsq-native-case-coverage-probe-v1", nodeid=item.nodeid,
                  worker=getattr(item.config, "workerinput", {}).get("workerid", "main"),
                  phase="after fixture Finish, before original NativeCollector.end_case/merge/cleanup",
                  managed_native_inputs_already_processed=collector.inputs, target_origin=origin, native_exports=observed,
                  implementation_SHA256={key: sha_file(path) for key, path in files.items()},
                  retention="compact native export counts, hashes and fixed target bitmap only; no cycle trace, raw per-case copy or source snapshot",
                  limits="Read-only coverage diagnostic, not a stimulus/oracle, proof of initialization, coverage waiver or LSQ acceptance.")
    output = factory.output / "native-case-coverage-summary.json"
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
