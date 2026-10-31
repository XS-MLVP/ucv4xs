"""Bounded source-proof audit; never modifies RTL or formal pytest reports."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from suites.frontend.bpu.tage.coverage.coverage_audit import ROOT
from suites.frontend.bpu.tage.coverage.coverage_audit import SOURCE
from suites.frontend.bpu.tage.coverage.coverage_audit import audit_key_copies


def run() -> dict[str, object]:
    protected = ("feature-points.json", "rtl-coverage-manifest.json",
                 "rtl-line-coverage.json", "verification-report.html")
    before = {name: sha256((ROOT / "results" / name).read_bytes()).hexdigest() for name in protected}
    report = audit_key_copies()
    source = ROOT / SOURCE
    original = source.read_text().splitlines()
    real_read = Path.read_text
    controls = []
    mutations = (
        ("remove_priority_exclusion", 1535, "if (hit) begin"),
        ("weaken_clean_guard", 538, "_GEN_54 = ~hitWritten | _GEN_44;"),
        ("wrong_target_row", 1545, "entries_0_0_entry_tag <= io_write_0_bits_entry_tag;"),
        ("wrong_source_port", 1637, "entries_1_3_entry_tag <= io_write_1_bits_entry_tag;"),
    )
    for name, line, replacement in mutations:
        changed = list(original)
        changed[line - 1] = replacement
        changed_source = "\n".join(changed)

        def read(path, *args, **kwargs):
            return changed_source if path == source else real_read(path, *args, **kwargs)

        with patch.object(Path, "read_text", read):
            try:
                audit_key_copies()
            except AssertionError:
                controls.append({"mutation": name, "line": line, "rejected": True})
            else:
                raise AssertionError(("proof accepted a corrupted source", name, line))
    after = {name: sha256((ROOT / "results" / name).read_bytes()).hexdigest() for name in protected}
    assert before == after and source.read_text().splitlines() == original
    report.update(source_mutation_negative_controls=controls,
                  source_mutations_are_in_memory_only=True,
                  formal_reports_preserved_byte_for_byte=True,
                  protected_sha256=before,
                  repeatable_command="python3 tests/tage/diagnostics/key_copy_audit.py --report /tmp/tage-key-copy-audit.json")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    result = run()
    rendered = json.dumps(result, indent=2) + "\n"
    if arguments.report is not None:
        assert arguments.report.resolve() not in {
            ROOT / SOURCE,
            *(ROOT / "results" / name for name in result["protected_sha256"]),
        }, "the diagnostic output cannot overwrite source or formal evidence"
        arguments.report.write_text(rendered)
    print(json.dumps({key: result[key] for key in (
        "raw_uncovered_source_lines", "additional_classified_assignment_lines",
        "combined_classified_assignment_lines", "not_classified_remaining_source_lines",
        "source_mutation_negative_controls", "formal_reports_preserved_byte_for_byte",
    )}, indent=2))
