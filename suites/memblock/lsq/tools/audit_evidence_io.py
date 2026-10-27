"""Version compact derived reports without losing an intermediate revision."""
from hashlib import sha256
import json


def write_report(output, report):
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if output.exists():
        raw = output.read_bytes()
        if json.loads(raw) == report:
            return
        directory = output.parent / "audit-history"
        directory.mkdir(exist_ok=True)
        archive = directory / f"{output.stem}-{sha256(raw).hexdigest()}.json"
        if archive.exists():
            assert archive.read_bytes() == raw, "immutable audit history differs"
        else:
            with archive.open("xb") as stream:
                stream.write(raw)
    output.write_text(text)
