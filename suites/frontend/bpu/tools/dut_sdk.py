"""Keep each generated DUT's copied SDK at one native ABI/version.

Obsolete libraries and replaced links are moved to an explicit backup outside
the package. Never modify the system SDK or another DUT as a side effect.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('abtb', 'bpu', 'ittage', 'mbtb', 'ras', 'sc', 'tage', 'ubtb', 'uras', 'utage')
LIBRARY = 'libxspcomm.so.0.3.0'
EXTENSION = '_pyxspcomm.so.0.3.0'
LINKS = {'libxspcomm.so': 'libxspcomm.so.3',
         'libxspcomm.so.3': LIBRARY, '_pyxspcomm.so': EXTENSION}


def _elf(path):
    return subprocess.check_output(['readelf', '-d', str(path)], text=True)


def inspect_sdk(sdk):
    sdk = Path(sdk)
    if sdk.is_symlink() or not sdk.is_dir() or (sdk / 'xspcomm').exists():
        raise ValueError(f'not a single copied SDK directory: {sdk}')
    for name in ('__init__.py', 'pyxspcomm.py', LIBRARY, EXTENSION):
        path = sdk / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'missing canonical SDK file: {path}')
    if 'Library soname: [libxspcomm.so.3]' not in _elf(sdk / LIBRARY):
        raise ValueError(f'canonical library is not ABI 3: {sdk}')
    if 'Shared library: [libxspcomm.so.3]' not in _elf(sdk / EXTENSION):
        raise ValueError(f'canonical Python extension does not require ABI 3: {sdk}')
    return {name: sha256((sdk / name).read_bytes()).hexdigest()
            for name in (LIBRARY, EXTENSION)}


def validate_sdk(sdk):
    identities = inspect_sdk(sdk)
    sdk = Path(sdk)
    allowed = set(LINKS) | {LIBRARY, EXTENSION}
    native = {p.name for p in sdk.iterdir()
              if p.name.startswith(('libxspcomm.so', '_pyxspcomm.so'))}
    if native != allowed:
        raise ValueError(f'mixed/incomplete native SDK files in {sdk}: {sorted(native ^ allowed)}')
    for name, target in LINKS.items():
        path = sdk / name
        if not path.is_symlink() or str(path.readlink()) != target:
            raise ValueError(f'non-canonical SDK link: {path}; expected {target}')
    return identities


def normalize_sdk(sdk, backup):
    """Validate first; preserve bytes, names and original symlink targets."""
    sdk, backup = Path(sdk), Path(backup)
    identities = inspect_sdk(sdk)
    if backup.exists() or backup.is_symlink() or backup.resolve().is_relative_to(sdk.resolve()):
        raise ValueError(f'backup must be a new directory outside SDK: {backup}')
    keep = {LIBRARY, EXTENSION} | set(LINKS)
    obsolete = sorted(p for p in sdk.iterdir()
                      if p.name.startswith(('libxspcomm.so', '_pyxspcomm.so')) and p.name not in keep)
    replace = [sdk / name for name, target in LINKS.items()
               if not (sdk / name).is_symlink() or str((sdk / name).readlink()) != target]
    backup.mkdir(parents=True)
    moved, created = [], []
    try:
        for path in obsolete + replace:
            if path.exists() or path.is_symlink():
                shutil.move(str(path), str(backup / path.name))
                moved.append(path.name)
        for path in replace:
            path.symlink_to(LINKS[path.name])
            created.append(path)
        if validate_sdk(sdk) != identities:
            raise ValueError('canonical SDK bytes changed during normalization')
    except BaseException:
        for path in reversed(created):
            path.unlink()  # Only links created by this operation.
        for name in reversed(moved):
            shutil.move(str(backup / name), str(sdk / name))
        raise
    return dict(sdk=str(sdk), backup=str(backup), moved=moved,
                canonical_sha256=identities, links=LINKS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--dut', choices=MODULES, nargs='+', default=list(MODULES))
    args = parser.parse_args()
    if len(set(args.dut)) != len(args.dut):
        parser.error('duplicate DUT')
    backup = args.backup.resolve()
    if backup.exists() or backup.is_relative_to(ROOT / 'dut'):
        parser.error('backup must be a new directory outside dut/')
    # Preflight every package before changing the first one.
    identities = [inspect_sdk(ROOT / 'dut' / name / 'xspcomm') for name in args.dut]
    # The SWIG extension may have a different build-id/RPATH after installation;
    # do not replace a working extension merely to make its file hash identical.
    if any(value[LIBRARY] != identities[0][LIBRARY] for value in identities):
        raise ValueError('selected DUTs contain different canonical ABI 3 libraries')
    reports = [normalize_sdk(ROOT / 'dut' / name / 'xspcomm', backup / name) for name in args.dut]
    (backup / 'receipt.json').write_text(json.dumps(dict(duts=reports), indent=2) + '\n')
    print(json.dumps(dict(normalized=args.dut, recoverable_backup=str(backup))))


if __name__ == '__main__':
    main()
