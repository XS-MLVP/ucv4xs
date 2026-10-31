"""Read actual native FST captures; never reconstruct waves from event logs."""
from pathlib import Path
import shutil
import subprocess


def convert_fst(fst, vcd):
    """Keep both reader output and errors, and reject unreadable captures."""
    fst, vcd = Path(fst), Path(vcd)
    reader = shutil.which('fst2vcd')
    if reader is None:
        raise RuntimeError('fst2vcd is required to validate native waveform captures')
    with vcd.open('w') as output:
        result = subprocess.run([reader, str(fst.resolve())], stdout=output, stderr=subprocess.PIPE, text=True)
    vcd.with_suffix('.stderr.txt').write_text(result.stderr)
    if result.returncode:
        raise AssertionError(f'FST reader failed ({result.returncode}): {result.stderr.strip()}')
    return vcd


def read_public_samples(vcd, names, *, module='VAGQDut_top'):
    """Return end-of-timestamp snapshots for selected actual public VCD leaves.

    This is a waveform parser, not a model of the DUT or its clocks. Repeated
    values persist between native timestamps; unknowns remain None.
    """
    names = tuple(names)
    wanted = set(names)
    scopes = []
    code_names = {}
    found = set()
    values = {name: None for name in names}
    samples = []
    time = None
    in_header = True
    with Path(vcd).open() as stream:
        for raw in stream:
            line = raw.strip()
            if not line:
                continue
            if in_header:
                fields = line.split()
                if fields[0] == '$scope':
                    scopes.append(fields[2])
                elif fields[0] == '$upscope':
                    scopes.pop()
                elif fields[0] == '$var':
                    code, name = fields[3:5]
                    if name in wanted and scopes and scopes[-1] == module:
                        code_names.setdefault(code, []).append(name)
                        found.add(name)
                elif fields[0] == '$enddefinitions':
                    missing = wanted - found
                    if missing:
                        raise AssertionError(f'Public waveform leaves missing: {sorted(missing)}')
                    in_header = False
                continue
            if line.startswith('#'):
                if time is not None:
                    samples.append({'time': time, 'values': dict(values)})
                time = int(line[1:])
                continue
            if line[0] in '01xXzZ':
                bits, code = line[0], line[1:]
            elif line[0] in 'bB':
                bits, code = line[1:].split()
            else:
                continue
            if code in code_names:
                value = None if any(bit in 'xXzZ' for bit in bits) else int(bits, 2)
                for name in code_names[code]:
                    values[name] = value
    if time is not None:
        samples.append({'time': time, 'values': dict(values)})
    if not samples or samples[-1]['time'] <= samples[0]['time']:
        raise AssertionError('FST contains no advancing native waveform timestamps')
    return samples
