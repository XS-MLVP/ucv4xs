"""Three-way reconciliation: spec intent vs Scala source vs generated DUT ports.

Why this exists
---------------
Semantics must come from the ISA/protocol contract. *Design intent* can only be
read from the Scala: the generated Verilog has `_GEN_6` and `uncacheState == 3'h3`,
and `--default-layer-specialization=disable` drops every `assert` (27 of them in
`NewStoreQueue.scala` survive only in the source; `$fatal` count in the generated
`PhysicalStoreQueue.sv`/`DeqModule.sv` is 0).  What can actually be driven and
observed, however, is only the generated DUT port surface.  Neither implementation
may define the expected answer, but both must agree about which fields exist.

A field that the Scala reads and the generated port does not carry must be
adjudicated: either it was trimmed on purpose (needs a reason) or it is
undriven/unconnected (a defect).  This tool produces that list.

Two modes
---------
``--report``  print the shape-level difference per DUT.  Shape level strips
              numeric lane indices and collapses parentheses on both sides
              (``io_x_0_bits_y`` == ``io_x_1_bits_y``), so vector indexing does
              not produce noise.  It also drops names that are only a *prefix*
              of a real port (wholesale bundle assignment) and Scala collection
              calls (``.map``/``.get``/``.head``).  The remaining output is for
              human triage, not an assertion.
``--strict``  validate ``manifest/critical-fields.json``: every field a
              functional point depends on must be declared present, or declared
              absent with a reason.  This is the part that gates a regression and
              it re-opens if the port surface later changes.

Exit status is 0 unless ``--strict`` finds an undeclared or contradicted field.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = __import__('suites.memblock.lsq', fromlist=['ROOT']).ROOT          # suites/memblock/lsq
REPO = ROOT.parents[2]                             # repository root
MANIFEST = ROOT / "manifest/critical-fields.json"

# Not preceded by a word char or a dot: `freeList.io.x` is a child module, not this IO.
IO_CHAIN = re.compile(r"(?<![\w.])io\.([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)")
INDEX = re.compile(r"[_]\d+(?=_|$)")
PAREN = re.compile(r"\((?:[A-Za-z_]\w*|\d+)\)")
CLASS = r"(?:abstract\s+)?class\s+{}\b"

#: Scala collection / utility members that follow a field name; they are not
#: part of the hardware field name, so the chain stops in front of them.
METHODS = frozenset("""
map flatMap filter filterNot exists forall foreach reduce reduceLeft reduceRight fold foldLeft
get getOrElse head last tail init size length isEmpty nonEmpty zip zipWithIndex lift apply
asUInt asBool asTypeOf orR andR xorR toSeq toList toSet sum count take drop slice sorted
reverse mkString iterator contains scan scanLeft distinct groupBy fire
""".split())


def dut_table():
    data = json.loads((ROOT / "manifest/duts.json").read_text())
    return data.get("duts", data)


def source_root():
    """Locate the locked XiangShan checkout used by this suite."""
    link = ROOT / "XiangShan"
    if link.exists():
        return link.resolve()
    local = REPO / ".ucv/local.json"
    if local.exists():
        cfg = json.loads(local.read_text())
        for key in ("source", "xiangshan", "sources"):
            if isinstance(cfg.get(key), str):
                path = Path(cfg[key]).expanduser()
                if (path / "src/main/scala").is_dir():
                    return path
    return None


def _class_span(text: str, top: str):
    """Return the (start, end) of the top's class body via brace matching."""
    pattern = re.compile(CLASS.format(re.escape(top)))
    match = pattern.search(text)
    if match is None:
        return None
    start = text.find("{", match.end())
    if start < 0:
        return None
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return start, index
    return None


def scala_file_for(top: str, src: Path):
    """Resolve `class <Top>`; a lane suffix such as `_1` refers to the same class."""
    base = re.sub(r"_\d+$", "", top)
    pattern = re.compile(CLASS.format(re.escape(base)))
    for path in sorted((src / "src/main/scala/xiangshan/mem").rglob("*.scala")):
        if pattern.search(path.read_text(errors="replace")):
            return path
    return None


def ports_of(dut: str):
    path = ROOT / "dut" / dut / "signals.json"
    if not path.exists():
        return None

    def walk(node, prefix=()):
        if "Pin" in node:
            yield "_".join(prefix)
        else:
            for key, child in node.items():
                if isinstance(child, dict):
                    yield from walk(child, (*prefix, key))

    return set(walk(json.loads(path.read_text())))


def shapes(names):
    return {INDEX.sub("", name) for name in names}


def scala_io_shapes(top: str, path: Path):
    text = PAREN.sub("", path.read_text(errors="replace"))
    span = _class_span(text, re.sub(r"_\d+$", "", top))
    body = text[span[0]:span[1]] if span else text
    names = set()
    for chain in IO_CHAIN.findall(body):
        parts = chain.split(".")
        kept = []
        for part in parts:
            if part in METHODS:
                break
            kept.append(part)
        if kept:
            names.add("io_" + "_".join(kept))
    return shapes(names)


def difference(dut: str, src: Path):
    top = dut_table()[dut]["top"]
    path = scala_file_for(top, src)
    ports = ports_of(dut)
    if path is None or ports is None:
        return None
    rtl = shapes(ports)
    scala = scala_io_shapes(top, path)
    # A name that is only a prefix of a real port is a wholesale bundle
    # assignment (`io.sbufferCtrl.req := ...`), not a missing field.
    scala_only = sorted(name for name in scala - rtl
                        if not any(port.startswith(name + "_") for port in rtl))
    return dict(dut=dut, top=top, scala_file=str(path.relative_to(src)),
                ports=len(ports), scala_only=scala_only,
                rtl_only=sorted(rtl - scala))


def report(src: Path, duts=None, limit=8):
    rows = []
    for dut in sorted(duts or dut_table()):
        item = difference(dut, src)
        if item is not None:
            rows.append(item)
    print(f"duts compared: {len(rows)}  scala-only shapes: {sum(len(r['scala_only']) for r in rows)}")
    for row in rows:
        print(f"\n== {row['dut']} ({row['top']}) ports={row['ports']} "
              f"scala_only={len(row['scala_only'])} rtl_only={len(row['rtl_only'])}")
        for name in row["scala_only"][:limit]:
            print("   only-scala:", name)
        if len(row["scala_only"]) > limit:
            print(f"   ... {len(row['scala_only']) - limit} more")
    return rows


def strict():
    if not MANIFEST.exists():
        return [f"missing manifest: {MANIFEST.relative_to(REPO)}"]
    problems = []
    for entry in json.loads(MANIFEST.read_text())["fields"]:
        dut, field, expect = entry["dut"], entry["field"], entry["expect"]
        if expect not in ("port", "absent"):
            problems.append(f"{dut}.{field}: bad expect {expect!r}")
            continue
        ports = ports_of(dut)
        if ports is None:
            problems.append(f"{dut}: no signals.json")
            continue
        present = field in ports
        if expect == "port" and not present:
            problems.append(f"{dut}.{field}: declared present but missing from the DUT ports")
        elif expect == "absent" and present:
            problems.append(f"{dut}.{field}: declared absent but now present; re-adjudicate "
                            f"(recorded reason: {entry.get('reason', '?')})")
        if expect == "absent" and not entry.get("reason"):
            problems.append(f"{dut}.{field}: absent without a reason")
        if expect == "port" and not entry.get("functional_point"):
            problems.append(f"{dut}.{field}: present without a functional_point")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--report", action="store_true", help="print the shape-level difference")
    parser.add_argument("--strict", action="store_true", help="validate manifest/critical-fields.json")
    parser.add_argument("--json", type=Path, help="write the report rows as JSON")
    parser.add_argument("--dut", action="append", help="restrict to one DUT (repeatable)")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    if not (args.report or args.strict):
        args.report = True
    src = source_root()
    if src is None:
        raise SystemExit("cannot locate the locked XiangShan checkout")
    if args.report:
        rows = report(src, args.dut, args.limit)
        if args.json:
            args.json.write_text(json.dumps(rows, indent=2) + "\n")
    problems = strict() if args.strict else []
    for problem in problems:
        print("ERROR", problem)
    if args.strict:
        print(f"strict: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
