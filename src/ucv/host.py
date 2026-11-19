"""Supported host platforms and architecture-specific tool acquisition. MPL-2.0.

Every native artifact this project installs or generates (the xcomm library,
Picker, Verilator, firtool, generated DUT packages) is tied to one machine
architecture. Build identities therefore include the architecture, and
acquisition refuses to hand out a binary built for a different one instead of
letting the loader fail later.
"""
from __future__ import annotations

import platform
import struct
from pathlib import Path

from .common import UcvError

# Architectures this host can build and run native artifacts for.
SUPPORTED_MACHINES = ('x86_64', 'aarch64')

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
    return system_name == 'Linux' and machine_name in SUPPORTED_MACHINES


def describe():
    return f'{system()} {machine()}'


def requirement():
    """Human-readable statement of what this host must satisfy."""
    return (f"Linux {' or '.join(SUPPORTED_MACHINES)}, Python 3.12")


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
        header = Path(path).read_bytes()[:20]
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
    expected = machine() if expected is None else expected
    found = elf_machine(path)
    if found is None:
        raise UcvError(f'Expected a Linux ELF binary at {path}; the file is not ELF')
    if found != expected:
        raise UcvError(f'{path} is built for {found}, but this host is {expected}; '
                       'provide a seed or build it from source for this architecture')
    return found


# --- Architecture-specific downloads --------------------------------------

MILL_DISTRIBUTION = '0.12.17'
MILL_LAUNCHER = (f'https://repo1.maven.org/maven2/com/lihaoyi/mill-dist/'
                 f'{MILL_DISTRIBUTION}/mill-dist-{MILL_DISTRIBUTION}-mill.sh')

# CIRCT publishes firtool for Linux x86_64 only. There is no linux-arm64
# asset in any released version, so aarch64 hosts must either supply their own
# build through ``local.json`` firtool, or take RTL from a released package
# instead of generating it.
FIRTOOL_VERSION = '1.149.0'
FIRTOOL_URLS = {
    'x86_64': (f'https://github.com/llvm/circt/releases/download/'
               f'firtool-{FIRTOOL_VERSION}/firrtl-bin-linux-x64.tar.gz'),
}


def firtool_url(machine_name=None):
    """Download URL for a native firtool, or ``None`` when none is published."""
    machine_name = machine() if machine_name is None else canonical(machine_name)
    return FIRTOOL_URLS.get(machine_name)


def rtl_generation_available(machine_name=None):
    return firtool_url(machine_name) is not None
