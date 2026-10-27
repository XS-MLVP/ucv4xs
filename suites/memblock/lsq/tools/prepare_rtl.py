#!/usr/bin/env python3
"""Extract a pinned generated-module closure without editing its RTL bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
MODULE = re.compile(r"^module\s+(\w+)", re.M)
INSTANCE = re.compile(r"^[ \t]*(\w+)[ \t]+(?:#\s*\([^;]*?\)\s*)?(\w+)[ \t]*\(", re.M)
KEYWORDS = set("module input output inout wire reg logic assign always always_ff always_comb always_latch initial if else case casez casex endcase for while return begin end function endfunction automatic task endtask generate endgenerate genvar parameter localparam typedef struct enum packed signed unsigned unique priority default break continue wait disable forever repeat".split())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_index():
    baseline = json.loads((ROOT / "manifest/baseline.json").read_text())
    rtl = (ROOT / baseline["rtl"]["directory_relative_to_verification_root"]).resolve()
    manifest = ROOT / "manifest/lsq-rtl.sha256"
    if digest(manifest) != baseline["lsq_static_closure"]["hash_manifest_content_sha256"]:
        raise RuntimeError("LSQ hash manifest changed")
    hashes, providers, children = {}, {}, {}
    for line in manifest.read_text().splitlines():
        sha, name = line.split("  ", 1)
        path = rtl / name
        if digest(path) != sha:
            raise RuntimeError(f"source RTL differs from baseline: {name}")
        hashes[name] = sha
        text = path.read_text()
        body = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        body = re.sub(r"//[^\n]*", "", body)
        children[name] = {m for m, _ in INSTANCE.findall(body) if m not in KEYWORDS}
        for module in MODULE.findall(text):
            if module in providers:
                raise RuntimeError(f"ambiguous generated module: {module}")
            providers[module] = name
    return rtl, hashes, providers, children


def write_owned(path: Path, contents: str) -> None:
    if path.exists() and path.read_text() != contents:
        raise RuntimeError(f"refusing to overwrite differing existing file: {path}")
    if not path.exists():
        path.write_text(contents)


def prepare(key: str) -> dict:
    specs = json.loads((ROOT / "manifest/duts.json").read_text())["duts"]
    spec = specs[key]
    rtl, hashes, providers, children = pinned_index()
    todo, seen, needed = [spec["top"]], set(), set()
    while todo:
        module = todo.pop()
        if module in seen:
            continue
        seen.add(module)
        if module not in providers:
            raise RuntimeError(f"unresolved module: {module}")
        name = providers[module]
        needed.add(name)
        todo.extend(children[name] - seen)
    dest = ROOT / "rtl" / key
    dest.mkdir(parents=True, exist_ok=True)
    for name in sorted(needed):
        target = dest / name
        if target.exists() and digest(target) != hashes[name]:
            raise RuntimeError(f"existing DUT RTL has different bytes: {target}")
        if not target.exists():
            shutil.copy2(rtl / name, target)
        if digest(target) != hashes[name]:
            raise RuntimeError(f"RTL copy hash mismatch: {target}")
    record = {"key": key, **spec, "files": {n: hashes[n] for n in sorted(needed)}}
    write_owned(dest / "filelist.f", "".join(n + "\n" for n in sorted(needed)))
    write_owned(dest / "source.json", json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("keys", nargs="+")
    for key in parser.parse_args().keys:
        row = prepare(key)
        print(f"{key}: {row['top']}, {len(row['files'])} pinned RTL files")
