"""Build native-memory DUTs without VPI or exported internal DPI getters.

Builds are isolated. Installation is a separate, recoverable operation after
the offset file, Python bindings and signal schema have been checked.
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess

if __package__:
    from tools.dut_sdk import normalize_sdk, validate_sdk
else:
    from dut_sdk import normalize_sdk, validate_sdk

ROOT = Path(__file__).resolve().parents[1]
MODULES = dict(abtb='AheadBtb', bpu='Bpu', ittage='Ittage', mbtb='MainBtb',
    ras='Ras', sc='Sc', tage='Tage', ubtb='MicroBtb', uras='MicroRas', utage='MicroTage')


def digest(path):
    with Path(path).open('rb') as stream:
        result = sha256()
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            result.update(chunk)
        return result.hexdigest()


def record(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')


def validate(package, name):
    top = name.capitalize() + 'Dut'
    required = ('__init__.py', 'signals.json', f'{top}_offset.yaml',
        f'_UT_{top}.so', f'libUT{top}.so', f'{top}.v')
    assert all((package / item).is_file() for item in required), (name, required)
    # A successful link is not enough: a failed SDK copy can leave an empty
    # namespace package, or a retry of `cp -r` can create xspcomm/xspcomm.
    native = ('__init__.py', 'pyxspcomm.py', '_pyxspcomm.so', 'libxspcomm.so.3')
    assert all((package / 'xspcomm' / item).is_file() for item in native), 'incomplete copied xspcomm binding'
    assert not (package / 'xspcomm/xspcomm').exists(), 'nested copied xspcomm binding'
    validate_sdk(package / 'xspcomm')
    wrapper = (package / '__init__.py').read_text()
    makefile = (package / 'Makefile').read_text()
    assert 'export RW_TYPE := MEM_DIRECT' in makefile and 'export VPI := OFF' in makefile
    assert 'export TRACE := fst' in makefile, 'trace metadata is required for read-only signal reconstruction'
    assert '--public-flat-rw' not in makefile, 'do not retain fields unnecessarily; use trace mappings'
    assert '.BindNativeData(' in wrapper and '.BindDPIPtr(' not in wrapper
    assert (package / f'{top}_offset.yaml').stat().st_size > 0
    assert '\nsignals:\n' in (package / f'{top}_offset.yaml').read_text(), 'trace signal map missing'
    old = ROOT / 'dut' / name
    assert json.loads((package / 'signals.json').read_text()) == json.loads((old / 'signals.json').read_text())
    assert digest(package / f'{top}.v') == digest(old / f'{top}.v'), 'predictor RTL changed'
    return {item: digest(package / item) for item in required}


def build(name, stage, jobs, *, retry=False):
    package = stage / 'dut' / name
    assert not package.exists(), ('refuse rebuilding or overwriting an existing attempt', package)
    module, top = MODULES[name], name.capitalize() + 'Dut'
    command = [str(ucv_paths.project_root() / '.tools/bin/picker'), 'export', module + '.sv', '--fs', 'filelist.f',
        '--sname', module, '--tname', top, '--tdir', str(package), '--rw', 'mem_direct',
        '-c', '-w', 'memory-direct.fst', '--vflag=--no-coverage-expr --no-coverage-fsm', '--lang', 'python',
        '--cp_lib', '1', '--autobuild', 'true', '-j', str(jobs)]
    env = dict(os.environ, VERILATOR_ROOT=str(ucv_paths.project_root() / '.tools/verilator/share/verilator'),
        PATH=__import__('ucv.config', fromlist=['Project']).Project().environment()['PATH'])
    started = datetime.now(timezone.utc).isoformat()
    suffix = '-retry-build' if retry else '-build'
    if retry:
        original = json.loads((stage / (name + '-build.exit.json')).read_text())
        assert original['process_exitstatus'] == 1, 'retry requires a recorded failed original export'
    log = stage / (name + suffix + '.log')
    with log.open('x') as stream:
        child = subprocess.Popen(command, cwd=ROOT / 'rtl' / name, env=env,
            stdout=stream, stderr=subprocess.STDOUT)
        record(stage / (name + suffix + '.live.json'), dict(pid=child.pid, command=command, started_at=started))
        print(dict(phase='memory-direct-build', dut=name, pid=child.pid), flush=True)
        status = child.wait()
    report = dict(dut=name, pid=child.pid, command=command, started_at=started,
        finished_at=datetime.now(timezone.utc).isoformat(), observed_child_exitstatus=status,
        log=str(log), log_sha256=digest(log), access_mode='MEM_DIRECT', VPI=False)
    try:
        assert status == 0, ('picker export failed', status)
        assert 'Error: Test failed' not in log.read_text() and 'Traceback' not in log.read_text()
        normalize_sdk(package / 'xspcomm', stage / (name + suffix + '-sdk-backup'))
        report['package_sha256'] = validate(package, name)
    except Exception as error:
        report.update(process_exitstatus=1, error=repr(error))
    else:
        report['process_exitstatus'] = 0
    record(stage / (name + suffix + '.exit.json'), report)
    print(dict(dut=name, exitstatus=report['process_exitstatus'], log=str(log)), flush=True)
    return report['process_exitstatus']


def validated_build_settings(name, stage, identities):
    """Use the successful matching build log, never flags copied from an old DUT."""
    stage = Path(stage).resolve()
    suffix = next((kind for kind in ('-retry-build', '-resume-build', '-build')
                   if (stage / (name + kind + '.exit.json')).exists()), '-build')
    receipt_path = stage / (name + suffix + '.exit.json')
    if receipt_path.is_symlink():
        raise ValueError('build receipt must not be a symlink')
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get('dut') != name
            or type(receipt.get('process_exitstatus')) is not int or receipt['process_exitstatus'] != 0
            or type(receipt.get('observed_child_exitstatus')) is not int or receipt['observed_child_exitstatus'] != 0
            or receipt.get('package_sha256') != identities):
        raise ValueError('successful build receipt does not match the installed package')
    log = stage / (name + suffix + '.log')
    if receipt.get('log') != str(log) or log.is_symlink() or digest(log) != receipt.get('log_sha256'):
        raise ValueError('build log identity does not match its successful receipt')
    command = receipt.get('command')
    if (not isinstance(command, list) or any(not isinstance(value, str) for value in command)
            or '--rw' not in command or command.index('--rw') + 1 >= len(command)
            or command[command.index('--rw') + 1] != 'mem_direct'
            or '-c' not in command or '-w' not in command):
        raise ValueError('build command must enable memory-direct, coverage and trace')
    lines = log.read_text().splitlines()
    flags = [line.split(': ', 1)[1].split(';') for line in lines
             if line.startswith('-- Verilator flags: ')]
    traces = [line for line in lines if line.startswith('-- Verilator ') and ', trace option: ' in line]
    if (len(flags) != 1 or not flags[0] or any(not flag for flag in flags[0])
            or len(traces) != 1 or not traces[0].endswith(', trace option: TRACE_FST')
            or any(flag in ('--vpi', '--public-flat-rw') or flag.startswith(('--vpi=', '--public-flat-rw='))
                   for flag in flags[0])):
        raise ValueError('ambiguous or incompatible memory-direct build flags/trace')
    settings = dict(verilator_flags=flags[0],
        verilator_flags_scope='recorded CMake SIMULATOR_FLAGS; not complete Verilator argv',
        trace_feature='fst', coverage_feature=True,
        picker_export_command=command,
        build_receipt=dict(path=str(receipt_path), sha256=digest(receipt_path)),
        build_log=dict(path=str(log), sha256=digest(log)))
    if suffix == '-resume-build':
        original_path = stage / (name + '-build.exit.json')
        original = json.loads(original_path.read_text())
        if (receipt.get('resume_of') != dict(path=str(original_path), sha256=digest(original_path))
                or original.get('process_exitstatus') != 1 or original.get('command') != command
                or receipt.get('execution_command') != ['make', '-j', str(receipt.get('jobs'))]):
            raise ValueError('resumed build must reference its exact failed export and actual make command')
        settings.update(build_resume_of=receipt['resume_of'],
                        build_execution_command=receipt['execution_command'])
    return settings


def resume(name, stage, jobs):
    """Retry a failed generated Makefile without deleting intermediates/evidence."""
    package = stage / 'dut' / name
    original_path = stage / (name + '-build.exit.json')
    original = json.loads(original_path.read_text())
    command = original['command']
    assert original['dut'] == name and original['process_exitstatus'] == 1
    assert command[command.index('--tdir') + 1] == str(package)
    assert (package / 'Makefile').is_file() and not package.is_symlink()
    original_log = Path(original['log'])
    assert original_log == stage / (name + '-build.log') and digest(original_log) == original['log_sha256']
    copied = package / ('UT_' + name.capitalize() + 'Dut') / 'xspcomm'
    if copied.exists():
        # Picker's generated cp -r expects a new destination. Preserve the
        # previous copy rather than nesting a second package inside it.
        shutil.move(str(copied), str(stage / (name + '-resume-previous-xspcomm')))
    log = stage / (name + '-resume-build.log')
    execution_command = ['make', '-j', str(jobs)]
    env = dict(os.environ, VERILATOR_ROOT=str(ucv_paths.project_root() / '.tools/verilator/share/verilator'),
               PATH=__import__('ucv.config', fromlist=['Project']).Project().environment()['PATH'])
    started = datetime.now(timezone.utc).isoformat()
    with log.open('x') as stream:
        child = subprocess.Popen(execution_command, cwd=package, env=env,
                                 stdout=stream, stderr=subprocess.STDOUT)
        status = child.wait()
    report = dict(dut=name, command=command, execution_command=execution_command, jobs=jobs,
        resume_of=dict(path=str(original_path), sha256=digest(original_path)),
        pid=child.pid, started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
        observed_child_exitstatus=status, log=str(log), log_sha256=digest(log),
        access_mode='MEM_DIRECT', VPI=False)
    try:
        assert status == 0, ('incremental make failed', status)
        normalize_sdk(package / 'xspcomm', stage / (name + '-resume-build-sdk-backup'))
        report['package_sha256'] = validate(package, name)
    except Exception as error:
        report.update(process_exitstatus=1, error=repr(error))
    else:
        report['process_exitstatus'] = 0
    record(stage / (name + '-resume-build.exit.json'), report)
    print(dict(dut=name, exitstatus=report['process_exitstatus'], log=str(log)), flush=True)
    return report['process_exitstatus']


def install(name, stage):
    package = stage / 'dut' / name
    identities = validate(package, name)
    target, backup = ROOT / 'dut' / name, stage / 'backup-dut' / name
    if backup.exists() and (stage / (name + '-retry-build.exit.json')).exists():
        backup = stage / 'backup-dut-retry' / name
    assert target.is_dir() and not backup.exists()
    backup.parent.mkdir(exist_ok=True)
    provenance_path = target / 'build-provenance.json'
    provenance = json.loads(provenance_path.read_text())
    for field in ('build_resume_of', 'build_execution_command', 'build_retry_of'):
        provenance.pop(field, None)
    provenance.update(validated_build_settings(name, stage, identities))
    provenance.update(access_mode='MEM_DIRECT', VPI=False, internal_DPI_exports=False,
        generated_at=datetime.now(timezone.utc).isoformat(), export_directory=str(package),
        memory_direct_offset_sha256=identities[name.capitalize() + 'Dut_offset.yaml'],
        previous_package_backup=str(backup), memory_direct_package_sha256=identities)
    lock_path = ROOT / 'dependencies/versions.json'
    if lock_path.is_file():
        provenance['verification_dependencies'] = json.loads(lock_path.read_text())
    record(package / 'build-provenance.json', provenance)
    shutil.move(str(target), str(backup))
    try:
        shutil.move(str(package), str(target))
    except BaseException:
        shutil.move(str(backup), str(target))
        raise
    install_suffix = '-retry-install' if (stage / (name + '-install.exit.json')).exists() else '-install'
    record(stage / (name + install_suffix + '.exit.json'), dict(process_exitstatus=0, dut=name,
        installed=str(target), recoverable_backup=str(backup), access_mode='MEM_DIRECT', VPI=False,
        package_sha256=identities, finished_at=datetime.now(timezone.utc).isoformat()))
    print(dict(installed=name, access_mode='MEM_DIRECT', backup=str(backup)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--dut', choices=MODULES, nargs='+', required=True)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--parallel', type=int, default=2)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Retry failed generated Makefiles; preserve original logs/receipts')
    parser.add_argument('--retry', action='store_true', help='Regenerate a failed export after its package was moved; preserve prior receipts')
    args = parser.parse_args()
    assert args.stage.is_absolute() and args.stage.is_dir()
    assert args.stage != ROOT and not args.stage.is_relative_to(ROOT / 'dut')
    assert args.jobs > 0 and args.parallel > 0 and len(set(args.dut)) == len(args.dut)
    assert sum((args.install, args.resume, args.retry)) <= 1
    if args.install:
        for name in args.dut:
            install(name, args.stage)
    else:
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            operation = resume if args.resume else lambda name, stage, jobs: build(name, stage, jobs, retry=args.retry)
            statuses = list(pool.map(lambda name: operation(name, args.stage, args.jobs), args.dut))
        raise SystemExit(int(any(statuses)))


if __name__ == '__main__':
    main()
