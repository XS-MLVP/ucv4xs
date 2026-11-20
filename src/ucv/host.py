"""Supported host platforms and architecture-specific tool acquisition. MPL-2.0.

Every native artifact this project installs or generates (the xcomm library,
Picker, Verilator, firtool, generated DUT packages) is tied to one machine
architecture. Build identities therefore include the architecture, and
acquisition refuses to hand out a binary built for a different one instead of
letting the loader fail later.
"""
from __future__ import annotations

import platform
import shlex
import shutil
import struct
import subprocess
from pathlib import Path

from .common import UcvError

# Architectures this host can build and run native artifacts for.
SUPPORTED_MACHINES = ('x86_64', 'aarch64')
SUPPORTED_SYSTEMS = ('Linux', 'Darwin')

# Linux ELF e_machine values for the architectures we can recognise.
ELF_MACHINES = {
    0x03: 'x86',
    0x3E: 'x86_64',
    0x28: 'arm',
    0xB7: 'aarch64',
    0xF3: 'riscv',
}

_ALIASES = {'amd64': 'x86_64', 'x64': 'x86_64', 'arm64': 'aarch64',
            'armv8l': 'aarch64', 'aarch64_be': 'aarch64'}


def canonical(machine_name):
    """Canonical architecture name for a reported one.

    Every entry point funnels through here so a caller passing
    ``platform.machine()`` directly gets the same answer as one passing
    nothing at all.
    """
    raw = str(machine_name).lower()
    return _ALIASES.get(raw, raw)


def machine():
    """Canonical machine architecture of the running host."""
    return canonical(platform.machine())


def system():
    return platform.system()


def supported(machine_name=None, system_name=None):
    """Whether this host can build and run native DUT packages."""
    machine_name = machine() if machine_name is None else canonical(machine_name)
    system_name = system() if system_name is None else system_name
    return system_name in SUPPORTED_SYSTEMS and machine_name in SUPPORTED_MACHINES


def describe():
    return f'{system()} {machine()}'


def requirement():
    """Human-readable statement of what this host must satisfy."""
    return (f"Linux or macOS (Darwin), {' or '.join(SUPPORTED_MACHINES)}, Python 3.12")


def require(machine_name=None, system_name=None):
    """Raise unless the host can produce and run native artifacts here."""
    if supported(machine_name, system_name):
        return
    raise UcvError(f'The locked environment requires {requirement()}; '
                   f'this host reports {system_name or system()} '
                   f'{canonical(machine_name) if machine_name else machine()}')


def elf_machine(path):
    """Architecture recorded in an ELF binary, or ``None`` if it is not ELF."""
    try:
        with Path(path).open('rb') as stream:
            header = stream.read(20)
    except OSError:
        return None
    if len(header) < 20 or header[:4] != b'\x7fELF':
        return None
    order = '<' if header[5] == 1 else '>'
    return ELF_MACHINES.get(struct.unpack(order + 'H', header[18:20])[0])


def require_elf_machine(path, expected=None):
    """Reject a prebuilt binary that was compiled for another architecture.

    Seeds are copied into the project and then loaded by builds and runs, so a
    foreign binary must fail here with the reason instead of at load time.
    """
    expected = machine() if expected is None else canonical(expected)
    found = elf_machine(path)
    if found is None:
        raise UcvError(f'Expected a Linux ELF binary at {path}; the file is not ELF')
    if found != expected:
        raise UcvError(f'{path} is built for {found}, but this host is {expected}; '
                       'provide a seed or build it from source for this architecture')
    return found


MACHO_MACHINES = {7: 'x86', 0x01000007: 'x86_64', 12: 'arm', 0x0100000C: 'aarch64'}


def macho_machines(path):
    """Architectures in a thin or universal Mach-O binary; empty if malformed."""
    try:
        with Path(path).open('rb') as stream:
            header = stream.read(8)
            if len(header) != 8:
                return set()
            magic = header[:4]
            thin = {b'\xce\xfa\xed\xfe': '<', b'\xcf\xfa\xed\xfe': '<',
                    b'\xfe\xed\xfa\xce': '>', b'\xfe\xed\xfa\xcf': '>'}
            if magic in thin:
                code = struct.unpack(thin[magic] + 'I', header[4:8])[0]
                return {MACHO_MACHINES[code]} if code in MACHO_MACHINES else set()
            fat = {b'\xca\xfe\xba\xbe': ('>', 20), b'\xbe\xba\xfe\xca': ('<', 20),
                   b'\xca\xfe\xba\xbf': ('>', 32), b'\xbf\xba\xfe\xca': ('<', 32)}
            if magic not in fat:
                return set()
            order, size = fat[magic]
            count = struct.unpack(order + 'I', header[4:8])[0]
            if not 0 < count <= 64:
                return set()
            machines = set()
            for _ in range(count):
                entry = stream.read(size)
                if len(entry) != size:
                    return set()
                code = struct.unpack(order + 'I', entry[:4])[0]
                if code in MACHO_MACHINES:
                    machines.add(MACHO_MACHINES[code])
            return machines
    except OSError:
        return set()


def require_native_machine(path, expected=None, system_name=None):
    """Validate both OS binary format and architecture before copying a seed."""
    expected = machine() if expected is None else canonical(expected)
    system_name = system() if system_name is None else system_name
    if system_name == 'Linux':
        return require_elf_machine(path, expected)
    if system_name != 'Darwin':
        require(expected, system_name)
    found = macho_machines(path)
    if not found:
        raise UcvError(f'Expected a macOS Mach-O binary at {path}; the file is not Mach-O')
    if expected not in found:
        raise UcvError(f'{path} is built for {" or ".join(sorted(found))}, but this host is '
                       f'{expected}; provide a seed or build it from source for this architecture')
    return expected


def shared_library_suffix():
    return '.dylib' if system() == 'Darwin' else '.so'


def loaded_library_paths():
    """Actual native mappings used to enforce one DUT type per interpreter."""
    if system() == 'Darwin':
        import ctypes
        dyld = ctypes.CDLL(None)
        count = dyld._dyld_image_count
        count.argtypes = []
        count.restype = ctypes.c_uint32
        name = dyld._dyld_get_image_name
        name.argtypes = [ctypes.c_uint32]
        name.restype = ctypes.c_char_p
        return [path.decode(errors='surrogateescape') for index in range(count())
                if (path := name(index))]
    paths = []
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and fields[5].startswith('/'):
            paths.append(fields[5].removesuffix(' (deleted)'))
    return paths


def build_environment(env):
    """Expose installed Homebrew build dependencies without changing the shell.

    Bison and Flex are keg-only on macOS; /usr/bin/bison is too old for
    Verilator. CMake, configure and the generated Makefiles also need to find
    Homebrew's lz4 headers and libraries for the pinned Verilator FST writer.
    """
    env = dict(env)
    brew = shutil.which('brew', path=env.get('PATH')) if system() == 'Darwin' else None
    if not brew:
        return env
    result = subprocess.run([brew, '--prefix'], capture_output=True, text=True, env=env)
    if result.returncode:
        return env
    prefix = Path(result.stdout.strip())
    if not prefix.is_absolute() or not prefix.is_dir():
        return env
    bins = [prefix/'opt'/name/'bin' for name in ('bison', 'flex')]
    env['PATH'] = ':'.join([*(str(p) for p in bins if p.is_dir()), env.get('PATH', '')])
    env['CMAKE_PREFIX_PATH'] = ':'.join(filter(None, (str(prefix), env.get('CMAKE_PREFIX_PATH'))))
    includes = [prefix/'include']
    if (prefix/'opt/flex/include').is_dir():
        includes.insert(0, prefix/'opt/flex/include')
    for key, flag in (('CPPFLAGS', ' '.join('-I'+shlex.quote(str(p)) for p in includes)),
                      ('LDFLAGS', '-L'+shlex.quote(str(prefix/'lib')))):
        env[key] = ' '.join(filter(None, (env.get(key), flag)))
    return env


# --- Architecture-specific downloads --------------------------------------

MILL_DISTRIBUTION = '0.12.17'
MILL_LAUNCHER = (f'https://repo1.maven.org/maven2/com/lihaoyi/mill-dist/'
                 f'{MILL_DISTRIBUTION}/mill-dist-{MILL_DISTRIBUTION}-mill.sh')

# This pinned CIRCT release has Linux x64 and macOS arm64 assets. Other
# hosts need a local firtool build or a released RTL package.
FIRTOOL_VERSION = '1.149.0'
FIRTOOL_URLS = {
    ('Linux', 'x86_64'): (f'https://github.com/llvm/circt/releases/download/'
               f'firtool-{FIRTOOL_VERSION}/firrtl-bin-linux-x64.tar.gz'),
    ('Darwin', 'aarch64'): (f'https://github.com/llvm/circt/releases/download/'
               f'firtool-{FIRTOOL_VERSION}/firrtl-bin-macos-arm64.tar.gz'),
}


def firtool_url(machine_name=None, system_name=None):
    """Download URL for a native firtool, or ``None`` when none is published."""
    machine_name = machine() if machine_name is None else canonical(machine_name)
    system_name = system() if system_name is None else system_name
    return FIRTOOL_URLS.get((system_name, machine_name))


def rtl_generation_available(machine_name=None, system_name=None):
    return firtool_url(machine_name, system_name) is not None
