"""Bounded retention of native coverage, using Verilator's own merge semantics.

No counter, zero point, metadata field or coverage type is filtered. Individual
successful dumps are consumed only after an atomic native merge; failed test
dumps remain available. This is run evidence, not a cycle-by-cycle audit log.
"""
from __future__ import annotations

from collections import Counter
from collections import defaultdict
from contextvars import ContextVar
from contextvars import Token
from hashlib import file_digest
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Callable


_collector: ContextVar[NativeCoverageRun | None] = ContextVar('native_coverage_run', default=None)
_POINT = re.compile(rb"C '(.*)' ([0-9]+)\n?\Z")


def set_native_coverage_run(run: NativeCoverageRun | None) -> Token:
    return _collector.set(run)


def reset_native_coverage_run(token: Token) -> None:
    _collector.reset(token)


def collect_native_coverage(dut: str, path: Path) -> Path:
    run = _collector.get()
    return path if run is None else run.add(dut, path)


def native_coverage_path(dut: str, requested: Path) -> Path:
    """Allocate before construction, not after two DUTs wrote the same name."""
    run = _collector.get()
    if run is None:
        return requested
    if not run.owner or run.finished or run.error is not None:
        raise RuntimeError('native coverage has no active healthy pytest owner')
    if re.fullmatch(r'[a-z][a-z0-9_]*', dut) is None:
        raise ValueError(f'invalid DUT name: {dut!r}')
    directory = run.directory / 'active' / dut
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='dut-', suffix='.dat', dir=directory)
    os.close(descriptor)
    return Path(name)


def _fingerprint(path: Path) -> dict[str, object]:
    with path.open('rb') as stream:
        digest = file_digest(stream, 'sha256').hexdigest()
    return dict(size=path.stat().st_size, sha256=digest)


def _validate(path: Path) -> int:
    """The native processor ignores malformed lines; do not silently do so."""
    points = 0
    with path.open('rb') as stream:
        if stream.readline() != b'# SystemC::Coverage-3\n':
            raise ValueError(f'invalid native coverage header: {path}')
        for number, line in enumerate(stream, 2):
            match = _POINT.fullmatch(line)
            if match is None or int(match[2]) > 2**63 - 1:
                raise ValueError(f'invalid native coverage record: {path}:{number}')
            points += 1
    if not points:
        raise ValueError(f'empty native coverage: {path}')
    return points


class NativeCoverageRun:
    """One process's small pending batch and one aggregate per DUT.

    The pytest owner calls ``end_test`` after teardown, when failure status is
    known, then ``finish`` before publishing the run manifest. A raw file is
    moved to a unique spool name immediately: repeated fixture filenames can
    never overwrite a pending input. No pre-existing run directory is reused.
    """

    def __init__(self, directory: Path, *, batch_size: int = 16,
                 processor: Callable[[str], str] | None = None) -> None:
        if type(batch_size) is not int or batch_size < 1:
            raise ValueError('native coverage batch size must be a positive integer')
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=False)
        self.batch_size = batch_size
        if processor is None:
            from icacheverify.common.coverage.rtl import _coverage_tool
            processor = _coverage_tool
        self.processor = processor
        self.owner: str | None = None
        self.inputs: list[dict[str, object]] = []
        self.pending: dict[str, list[dict[str, object]]] = defaultdict(list)
        self.aggregates: dict[str, Path] = {}
        self.failures: set[str] = set()
        self.finished = False
        self.error: BaseException | None = None

    def add(self, dut: str, path: Path) -> Path:
        if self.error is not None:
            raise RuntimeError('native coverage run previously failed') from self.error
        if self.finished:
            raise RuntimeError('native coverage run is already finished')
        if not self.owner:
            raise RuntimeError('native coverage has no active pytest owner')
        if re.fullmatch(r'[a-z][a-z0-9_]*', dut) is None:
            raise ValueError(f'invalid DUT name: {dut!r}')
        path = Path(path).resolve(strict=True)
        points = _validate(path)
        identity = _fingerprint(path)
        spool = self.directory / 'pending' / dut / f'{len(self.inputs):08d}.dat'
        spool.parent.mkdir(parents=True, exist_ok=True)
        if spool.exists():
            raise FileExistsError(spool)
        # Both locations are within the same pytest result filesystem. rename
        # transfers ownership without copying a full coverage table.
        path.rename(spool)
        row = dict(dut=dut, nodeid=self.owner, original_path=str(path),
                   points=points, **identity, spool_path=str(spool))
        self.inputs.append(row)
        self.pending[dut].append(row)
        aggregate = self.directory / dut / 'native-merged.dat'
        self.aggregates[dut] = aggregate
        return aggregate

    def end_test(self, nodeid: str, *, failed: bool) -> None:
        if failed:
            self.failures.add(nodeid)
        if sum(map(len, self.pending.values())) >= self.batch_size:
            self.flush()
        self.owner = None

    def flush(self) -> None:
        if self.error is not None:
            raise RuntimeError('native coverage run previously failed') from self.error
        try:
            self._flush()
        except BaseException as error:
            self.error = error
            raise

    def _flush(self) -> None:
        for dut, rows in self.pending.items():
            if not rows:
                continue
            target = self.aggregates[dut]
            target.parent.mkdir(parents=True, exist_ok=True)
            sources = [Path(row['spool_path']) for row in rows]
            for row, path in zip(rows, sources):
                if _fingerprint(path) != {key: row[key] for key in ('size', 'sha256')}:
                    raise ValueError(f'native coverage input changed: {path}')
            descriptor, name = tempfile.mkstemp(prefix='.native-merge-', suffix='.dat', dir=target.parent)
            os.close(descriptor)
            temporary = Path(name)
            try:
                subprocess.run([self.processor(dut), '--write', str(temporary),
                                *([str(target)] if target.exists() else []),
                                *map(str, sources)], check=True, capture_output=True, text=True)
                _validate(temporary)
                with temporary.open('rb') as stream:
                    os.fsync(stream.fileno())
                temporary.replace(target)
                directory_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                temporary.unlink(missing_ok=True)
            # No input is consumed on processor, validation or publication
            # failure. Never glob/delete a shared result directory.
            committed = list(rows)
            rows.clear()
            for row, path in zip(committed, sources):
                if row['nodeid'] in self.failures:
                    retained = self.directory / 'failed' / dut / path.name
                    retained.parent.mkdir(parents=True, exist_ok=True)
                    path.rename(retained)
                    row['retained_path'] = str(retained)
                else:
                    path.unlink()
                del row['spool_path']

    def finish(self) -> dict[str, object]:
        self.flush()
        self.finished = True
        return dict(
            mode='merged', batch_size=self.batch_size, input_files=len(self.inputs),
            input_files_by_dut=dict(Counter(row['dut'] for row in self.inputs)),
            input_bytes=sum(row['size'] for row in self.inputs),
            retained_bytes=sum(path.stat().st_size for path in self.aggregates.values()) +
                sum(Path(row['retained_path']).stat().st_size for row in self.inputs if 'retained_path' in row),
            inputs=self.inputs,
            aggregates=[dict(dut=dut, path=str(path), **_fingerprint(path))
                        for dut, path in sorted(self.aggregates.items())],
        )
