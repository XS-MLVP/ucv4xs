"""Read the single Picker configuration database of a generated DUT. MPL-2.0.

Picker 3 replaced the ``signals.json`` port tree and ``<top>_offset.yaml``
address map with one ``<top>.xscfg`` database. That file is the only source of
truth, and ``picker config`` is its maintained reader, so suites ask it rather
than keeping derived copies of the same data.
"""
from __future__ import annotations

import json
from pathlib import Path

from .common import UcvError, execute

SECTIONS = {'metadata': 'm', 'variables': 'v', 'signals': 's',
            'types': 't', 'candidates': 'c'}


def database_path(directory):
    """Return the one configuration database inside a generated DUT package."""
    directory = Path(directory)
    found = sorted(directory.glob('*.xscfg'))
    if len(found) != 1:
        raise UcvError(f'expected exactly one .xscfg in {directory}, found {len(found)}')
    return found[0]


class Database:
    """Section views over one ``.xscfg``.

    ``ports`` is the RTL port tree (name, ``High``/``Low``, ``Pin``) that used
    to be ``signals.json``; ``variables`` is the addressable storage that used
    to be the ``variables`` list of ``<top>_offset.yaml``; ``signals`` holds the
    trace-derived projections. Picker 3 moved ``direct`` aliases out of the old
    ``signals`` list and into ``variables``, so a name lookup should consult
    ``variables`` first and fall back to ``signals``.
    """

    def __init__(self, path, picker=None):
        self.path = Path(path)
        self._picker = Path(picker) if picker else _default_picker()
        self._cache = {}

    def section(self, name):
        """One decoded section as a JSON object, cached for this database."""
        if name not in SECTIONS:
            raise UcvError(f'unknown configuration section: {name}')
        if name not in self._cache:
            result = execute([self._picker, 'config', self.path,
                              '--section', name], check=False)
            if result.returncode:
                raise UcvError(f'picker config {name} failed for {self.path}: '
                               f'{(result.stderr or result.stdout).strip()}')
            try:
                value = json.loads(result.stdout or '{}')
            except ValueError as error:
                raise UcvError(f'picker config {name} returned invalid JSON for '
                               f'{self.path}: {error}') from error
            self._cache[name] = value if isinstance(value, dict) else {}
        return self._cache[name]

    def record(self, name):
        """One metadata record such as ``ports`` or ``generator``."""
        value = self.section('metadata')
        if name not in value:
            raise UcvError(f'{self.path}: metadata has no record {name!r}')
        return value[name]

    @property
    def ports(self):
        """RTL port tree; structurally identical to the retired signals.json."""
        return self.record('ports')

    @property
    def generator(self):
        """Build identity recorded by Picker: simulator, rw_type, native_abi."""
        return self.record('generator')

    @property
    def port_types(self):
        """Port name to native layout id, for width-accurate binding."""
        return self.record('port_types')

    @property
    def variables(self):
        """Addressable signals: offset, mem_bytes, rtl_width, type, array_size."""
        return self.section('variables')

    @property
    def signals(self):
        """Trace-derived signals; ``direct`` names live in ``variables`` now."""
        return self.section('signals')

    @property
    def types(self):
        """Native layout definitions referenced by ``port_types`` and variables."""
        return self.section('types')

    def names(self, include_signals=True):
        """Every recorded name, variables first."""
        result = list(self.variables)
        if include_signals:
            result += [name for name in self.signals if name not in self.variables]
        return result

    def addressable(self, name):
        """Variable record for ``name``, or ``None`` when it is not addressable."""
        return self.variables.get(name)

    def lookup(self, name):
        """Variable record, else trace record, else ``None``."""
        return self.variables.get(name) or self.signals.get(name)


def _default_picker():
    from .runtime import tool_path
    return tool_path('picker')


_DATABASES = {}


def open_dut(directory):
    """Open the configuration database of an installed DUT package."""
    path = database_path(directory).resolve()
    if path not in _DATABASES:
        _DATABASES[path] = Database(path)
    return _DATABASES[path]


def ports(directory):
    """Port tree of an installed DUT package."""
    return open_dut(directory).ports


# --- Writer ---------------------------------------------------------------
# Picker is the only production writer. This exists so tests and controls can
# build a synthetic database instead of hand-writing a retired YAML layout;
# ``tests/test_xscfg.py`` checks the bytes it emits against ``picker config``.

MAGIC = b'XSCFGDB\x00'
FORMAT_VERSION = 1
HEADER_SIZE = 128
BLOCK_ENTRIES = 256


def _uint(value):
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _value(value):
    """Encode one JSON-shaped value using the format's tagged representation."""
    if value is None:
        return b'\x00'
    if isinstance(value, bool):
        return bytes([2 if value else 1])
    if isinstance(value, int):
        if value < 0:
            return bytes([4]) + _uint((-value << 1) - 1)
        return bytes([3]) + _uint(value)
    if isinstance(value, float):
        import struct
        return bytes([5]) + struct.pack('<d', value)
    if isinstance(value, str):
        raw = value.encode()
        return bytes([6]) + _uint(len(raw)) + raw
    if isinstance(value, list):
        return bytes([7]) + _uint(len(value)) + b''.join(_value(item) for item in value)
    if isinstance(value, dict):
        out = bytearray(b'\x08')
        keys = sorted(value, key=lambda key: key.encode())
        out += _uint(len(keys))
        for key in keys:
            raw = key.encode()
            out += _uint(len(raw)) + raw + _value(value[key])
        return bytes(out)
    raise UcvError(f'unsupported configuration value: {type(value).__name__}')


def _crc(data):
    import zlib
    return zlib.crc32(data) & 0xFFFFFFFF


def _hash(name):
    """Truncated 64-bit FNV-1a of the record key, as used by the index."""
    value = 0xCBF29CE484222325
    for byte in name.encode():
        value = ((value ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return value & 0xFFFFFFFF


def write_database(path, sections, model=''):
    """Write one ``.xscfg`` database.

    ``sections`` maps a section name (``metadata``, ``variables``, ``signals``,
    ``types``, ``candidates``) to a mapping of record name to JSON value.
    """
    entries = {}
    for section, records in sections.items():
        if section not in SECTIONS:
            raise UcvError(f'unknown configuration section: {section}')
        for name, value in records.items():
            entries[f'{SECTIONS[section]}:{name}'] = _value(value)
    if not entries:
        raise UcvError('a configuration database needs at least one record')
    keys = sorted(entries, key=lambda key: key.encode())

    blocks, indices, pending, previous = [], [], [], ''
    def flush():
        nonlocal pending, previous
        if not pending:
            return
        raw = bytearray(len(pending).to_bytes(4, 'little'))
        offset = 4 + len(pending) * 4
        for record in pending:
            raw += offset.to_bytes(4, 'little')
            offset += len(record)
        for record in pending:
            raw += record
        import zlib
        compressed = zlib.compress(bytes(raw), 6)
        if len(compressed) < len(raw):
            blocks.append((compressed, len(raw), _crc(bytes(raw)), 1))
        else:
            blocks.append((bytes(raw), len(raw), _crc(bytes(raw)), 0))
        pending, previous = [], ''

    for key in keys:
        payload = entries[key]
        if len(pending) == BLOCK_ENTRIES:
            flush()
        prefix = 0
        while prefix < min(len(previous), len(key)) and previous[prefix] == key[prefix]:
            prefix += 1
        suffix = key[prefix:].encode()
        indices.append((_hash(key), len(blocks), len(pending)))
        pending.append(_uint(prefix) + _uint(len(suffix)) + suffix + _uint(len(payload)) + payload)
        previous = key
    flush()

    indices.sort()
    directory = HEADER_SIZE + len(indices) * 8
    data_offset = directory + len(blocks) * 24
    header = bytearray(HEADER_SIZE)
    header[0:8] = MAGIC
    header[8:12] = FORMAT_VERSION.to_bytes(4, 'little')
    header[12:16] = HEADER_SIZE.to_bytes(4, 'little')
    header[24:32] = len(indices).to_bytes(8, 'little')
    header[32:40] = len(blocks).to_bytes(8, 'little')
    header[40:48] = HEADER_SIZE.to_bytes(8, 'little')
    header[48:56] = directory.to_bytes(8, 'little')
    header[56:64] = data_offset.to_bytes(8, 'little')
    encoded = model.encode()
    header[64:68] = len(encoded).to_bytes(4, 'little')
    header[68:68 + len(encoded)] = encoded

    index_bytes = bytearray()
    for hashed, block, slot in indices:
        index_bytes += hashed.to_bytes(4, 'little')
        index_bytes += ((block << 8) | slot).to_bytes(4, 'little')
    directory_bytes = bytearray()
    for payload, raw, checksum, codec in blocks:
        directory_bytes += data_offset.to_bytes(8, 'little')
        directory_bytes += len(payload).to_bytes(4, 'little')
        directory_bytes += raw.to_bytes(4, 'little')
        directory_bytes += checksum.to_bytes(4, 'little')
        directory_bytes += codec.to_bytes(4, 'little')
        data_offset += len(payload)
    header[16:24] = data_offset.to_bytes(8, 'little')
    header[120:124] = _crc(bytes(header[:120])).to_bytes(4, 'little')

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(header) + bytes(index_bytes) + bytes(directory_bytes)
                     + b''.join(payload for payload, *_ in blocks))
    return path
