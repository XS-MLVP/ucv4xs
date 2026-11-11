"""Pinned, byte-preserving whole-chip RTL imports. MPL-2.0."""
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile
import urllib.request

from .common import UcvError, digest, file_hash, lock, now, read, write


def release_spec(project, baseline):
    path = project.root / 'baselines/rtl-releases.json'
    entries = read(path).get('releases', {}) if path.is_file() else {}
    entry = entries.get(baseline['name'])
    if entry is None:
        raise UcvError(f"No pinned RTL release for {baseline['name']}; use --rtl-source source to generate explicitly")
    if entry.get('baseline_sha256') != digest(baseline):
        raise UcvError('RTL release does not match the complete baseline: ' + baseline['name'])
    if (not re.fullmatch(r'[0-9a-f]{64}', entry.get('sha256', ''))
            or not entry.get('url', '').startswith('https://')
            or not re.fullmatch(r'[\w.-]+', entry.get('package', ''))
            or entry['package'] in {'.','..'}):
        raise UcvError('Invalid RTL release lock: ' + baseline['name'])
    return entry


def release_directory(project, baseline):
    return project.root / '.cache/releases' / digest(release_spec(project, baseline))


def validate_parameters(parameters, baseline):
    source = parameters.get('source', {})
    generation = parameters.get('generation', {})
    expected = {'repository': baseline['repository'], 'commit': baseline['commit'],
                'patches': baseline['patches'],
                'recursive_submodules': len(baseline['recursive_submodules'])}
    if (any(source.get(k) != v for k, v in expected.items())
            or parameters.get('design') != baseline['design']
            or any(parameters.get('tools', {}).get(k) != v for k, v in baseline['tools'].items())
            or generation.get('firtool_options') != baseline['firtool_options']
            or any(generation.get(k) != baseline['design'].get(k, [])
                   for k in ('top', 'config', 'num_cores', 'chisel_args'))
            or generation.get('target') != 'systemverilog'
            or generation.get('split_verilog') is not True):
        raise UcvError('BUILD-PARAMETERS.json disagrees with the locked baseline')


def unpack(archive, destination, entry, baseline):
    """Extract only regular files/directories, then check every packaged file."""
    with tarfile.open(archive) as stream:
        seen = set()
        for member in stream.getmembers():
            name = PurePosixPath(member.name)
            if (name.is_absolute() or '..' in name.parts or not name.parts
                    or name.parts[0] != entry['package']
                    or not (member.isdir() or member.isfile()) or name in seen):
                raise UcvError('Unsafe or duplicate release member: ' + member.name)
            seen.add(name)
        stream.extractall(destination, filter='data')
    root = destination / entry['package']
    checksums = {}
    for line in (root / 'SHA256SUMS').read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64}) [ *](.+)', line)
        if not match:
            raise UcvError('Malformed SHA256SUMS')
        name = PurePosixPath(match[2])
        if name.is_absolute() or '..' in name.parts or str(name) in checksums:
            raise UcvError('Unsafe or duplicate checksum path: ' + str(name))
        checksums[str(name)] = match[1]
    actual = {str(p.relative_to(root)): file_hash(p) for p in root.rglob('*')
              if p.is_file() and p.name != 'SHA256SUMS'}
    if checksums != actual:
        raise UcvError('Release file set or SHA256SUMS mismatch')
    validate_parameters(read(root / 'BUILD-PARAMETERS.json'), baseline)
    rtl = root / 'rtl'
    files = (rtl / 'filelist.f').read_text().splitlines()
    for value in files:
        name = PurePosixPath(value)
        if name.is_absolute() or '..' in name.parts or not (rtl / name).is_file():
            raise UcvError('Invalid release filelist entry: ' + value)
    if not files:
        raise UcvError('Empty release filelist')
    return {**actual, 'SHA256SUMS': file_hash(root / 'SHA256SUMS')}


def fetch_release(project, baseline, archive=None):
    entry = release_spec(project, baseline)
    destination = release_directory(project, baseline)
    with lock(project.root / '.cache/locks' / ('release-' + destination.name)):
        if archive and file_hash(archive) != entry['sha256']:
            raise UcvError('RTL archive SHA-256 mismatch')
        receipt = destination / 'release.json'
        if receipt.is_file():
            record = read(receipt)
            root = destination / entry['package']
            actual = {str(p.relative_to(root)): file_hash(p) for p in root.rglob('*') if p.is_file()}
            if (record.get('release') != entry or record.get('baseline') != baseline
                    or record.get('files') != actual):
                raise UcvError('RTL release cache is corrupt: ' + str(destination))
            return root / 'rtl'
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='import-', dir=destination.parent) as temp:
            stage = Path(temp)
            payload = Path(archive) if archive else stage / 'download.tar.gz'
            if not archive:
                request = urllib.request.Request(entry['url'], headers={'User-Agent': 'ucv4xs'})
                with urllib.request.urlopen(request, timeout=60) as response, payload.open('wb') as output:
                    shutil.copyfileobj(response, output)
            if file_hash(payload) != entry['sha256']:
                raise UcvError('RTL archive SHA-256 mismatch')
            imported = stage / 'imported'
            imported.mkdir()
            files = unpack(payload, imported, entry, baseline)
            write(imported / 'release.json', {'schema': 1, 'origin': 'release', 'release': entry,
                  'baseline': baseline, 'files': files, 'imported_at': now()})
            # Publish only after all checks; interrupted downloads never become cache hits.
            if destination.exists():
                raise UcvError('Incomplete release destination already exists: ' + str(destination))
            imported.rename(destination)
    return destination / entry['package'] / 'rtl'
