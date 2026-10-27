#!/usr/bin/env python3
"""Record launch-source equality at completion without rewriting history."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def capture(name):
    run = ROOT / "results" / name
    files = json.loads((run / "source-evidence.json").read_text())["files"]
    differences = []
    for relative, want in files.items():
        for kind, path in (("snapshot", run / "verification-source" / relative), ("current", ROOT / relative)):
            got = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            if got != want:
                differences.append({"path": relative, "kind": kind, "expected": want, "actual": got})
    report = {"verification_snapshot_files": len(files), "all_current_launch_files_match_snapshot": not differences, "files": files, "differences": differences}
    out = run / "end-source-check.json"
    if out.exists():
        assert json.loads(out.read_text()) == report, "refusing to overwrite historical end-source evidence"
    else:
        with out.open("x") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
    print(json.dumps({key: value for key, value in report.items() if key != "files"}, indent=2))
    assert not differences


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    capture(parser.parse_args().name)
