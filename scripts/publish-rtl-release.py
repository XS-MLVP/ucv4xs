#!/usr/bin/env python3
"""Stage a whole-chip RTL release package for a named baseline. MPL-2.0.

Publishes the complete XiangShan RTL for one commit, not a module closure: a
module UT verdict is one verification record for this RTL, not its scope. Takes
the file set from the whole-chip generation cache and never assembles it from
DUT closures.

The script only stages and packs. Lint verification and the upload stay manual,
because both need the network and are visible outside this repository; see the
"发布生成 RTL 包" section of skills/ucv4xs-workflow/SKILL.md.
"""
import argparse
import gzip
import json
import shutil
import sys
import tarfile

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from ucv.common import UcvError, digest, file_hash, now  # noqa: E402
from ucv.config import Project  # noqa: E402
from ucv.sources import generation_spec  # noqa: E402

def generation_directory(project, baseline):
    """Whole-chip generation cache for one baseline, verified against its receipt."""
    directory = project.root / '.cache/generated' / digest(generation_spec(baseline))
    receipt = directory / 'generation.json'
    if not receipt.is_file():
        raise UcvError(
            f'No whole-chip generation for {baseline["name"]} at {directory}; '
            'run ucv prepare --rtl-source source first. A module closure from '
            '.cache/duts is not a release source.')
    record = json.loads(receipt.read_text())
    recorded = record['spec']['baseline']
    if recorded['commit'] != baseline['commit'] or recorded['name'] != baseline['name']:
        raise UcvError(f'Generation cache belongs to {recorded["name"]}, not {baseline["name"]}')
    rtl = directory / 'rtl'
    missing = [str(rtl / name) for name in record['rtl'] if not (rtl / name).is_file()]
    if missing:
        raise UcvError(f'Generation cache is incomplete: {len(missing)} RTL files missing')
    return directory, record


def file_inventory(rtl):
    """Authoritative package contents: firtool's filelist plus what it lists.

    Some firtool entries carry a ``./`` prefix. Compare by normalised name but
    keep the original lines: the filelist is the authoritative compile order and
    rewriting it would make the package incomparable with the upstream product.
    """
    filelist = rtl / 'filelist.f'
    if not filelist.is_file():
        raise UcvError(f'Missing firtool filelist: {filelist}')
    entries = [line for line in filelist.read_text().splitlines() if line.strip()]
    for entry in entries:
        if not (rtl / entry).is_file():
            raise UcvError(f'filelist entry has no file: {entry}')
    listed = {Path(entry).as_posix().removeprefix('./') for entry in entries}
    sv = sorted(p.name for p in rtl.glob('*.sv'))
    verilog = sorted(p.name for p in rtl.glob('*.v'))
    unlisted = sorted(set(sv + verilog) - listed)
    if unlisted:
        raise UcvError(f'{len(unlisted)} RTL files are absent from filelist.f: {unlisted[:5]}')
    return {'sv': sv, 'v': verilog, 'entries': entries}


def count_occurrences(path, needle, chunk=1 << 20):
    """Count a byte pattern without materialising the file.

    The dumped FIRRTL is around 1.8 GB, so reading it whole would cost more
    memory than the rest of this script combined. The window keeps a needle
    length of overlap so a match spanning a chunk boundary is still found.
    """
    pattern = needle.encode()
    overlap = len(pattern) - 1
    total, carry = 0, b''
    with path.open('rb') as stream:
        while True:
            block = stream.read(chunk)
            if not block:
                break
            window = carry + block
            total += window.count(pattern)
            carry = window[-overlap:] if overlap else b''
    return total


def assertion_counts(generation):
    """Chisel assertions retained in FIRRTL versus $fatal in SystemVerilog."""
    fir = next((generation / 'rtl').glob('*.fir'), None)
    fir_assertions = None
    if fir is not None:
        # Same measure the earlier package used: chisel's assert lowering.
        fir_assertions = count_occurrences(fir, 'circt_chisel_ifelsefatal')
    fatal = sum(count_occurrences(path, '$fatal')
                for path in (generation / 'rtl').glob('*.sv'))
    return fir_assertions, fatal


def tool_versions(project, baseline):
    tools = dict(baseline['tools'])
    pin = project.tools.get('verilator', {})
    if pin:
        tools['verilator'] = {'version': pin['version'], 'repository': pin['repository'],
                              'ref': pin['ref']}
    return tools


def build_parameters(project, baseline, generation, record, inventory, package):
    fir_assertions, fatal = assertion_counts(generation)
    source = {
        'repository': baseline['repository'],
        'commit': baseline['commit'],
        'recursive_submodules': len(baseline['recursive_submodules']),
        'patches': baseline['patches'],
    }
    if baseline.get('branch'):
        source['branch'] = baseline['branch']
    design = baseline['design']
    return {
        'package': package,
        'description': (f'Generated RTL for XiangShan commit {baseline["commit"]}, '
                        f'{design["config"]}, release configuration '
                        f'(equivalent to `make verilog`).'),
        'generated_at': record.get('completed_at', now()),
        'source': source,
        'design': design,
        'generation': {
            'top': design['top'],
            'config': design['config'],
            'num_cores': design['num_cores'],
            'target': 'systemverilog',
            'split_verilog': True,
            'dump_fir': True,
            'chisel_args': design.get('chisel_args', []),
            'firtool_options': baseline['firtool_options'],
            'equivalent_upstream_target': 'make verilog',
            'verbatim_command': record['command'],
        },
        'tools': tool_versions(project, baseline),
        'contents': {
            'rtl/*.sv': len(inventory['sv']),
            'rtl/*.v': len(inventory['v']),
            'rtl/filelist.f': 1,
            'filelist_entries': len(inventory['entries']),
            'top_module': 'XSTop',
            'hierarchy': 'XSTop -> XSTile -> {XSCore -> {Frontend, Backend, MemBlock}, L2Top}',
        },
        'assertions': {
            'chisel_assertions_in_firrtl': fir_assertions,
            'systemverilog_fatal': fatal,
            'reason': '--default-layer-specialization=disable drops the verification/assert layer',
            'consequence': ('RTL contains no $fatal/$error; invariant checking must come '
                            'from the testbench'),
        },
        'difftest': {
            'required': False,
            'note': (f'{len([name for name in inventory["v"] if name.startswith("DiffExt")])} '
                     'DiffExt*.v are guarded by `ifdef DIFFTEST and compile to empty '
                     'modules without it'),
            'if_enabled': ('requires DifftestMacros.svh and the difftest C++ library, '
                           'which are not included'),
        },
        'differences_from_make_verilog': {
            'git_header_comment': ('absent; the Makefile prepends `// <commit>` and '
                                   '`// <git diff>` to the top file'),
            'rtl_content': 'identical',
        },
    }


def readme(baseline, parameters_doc, package):
    design = baseline['design']
    contents = parameters_doc['contents']
    return f"""# XiangShan RTL @ {baseline['commit'][:9]}

香山提交 `{baseline['commit']}` 的完整生成 RTL（SystemVerilog），
{design['config']}，{design['num_cores']} 核，release 配置，等价于上游 `make verilog`。

## 内容

```
rtl/
├── filelist.f      firtool 生成的编译清单（{contents['filelist_entries']} 项，依赖顺序）
├── *.sv            {contents['rtl/*.sv']} 个
└── *.v             {contents['rtl/*.v']} 个 DPI 桩（difftest 与提交号打印）
```

顶层 `XSTop`，层次 `XSTop → XSTile → {{XSCore → {{Frontend, Backend, MemBlock}}, L2Top}}`。

生成参数、工具版本和逐字节命令见 `BUILD-PARAMETERS.json`。

## 使用

`filelist.f` 里是相对 `rtl/` 的文件名，先进入该目录：

```sh
cd rtl
verilator --lint-only -Wno-fatal -f filelist.f --top-module XSTop -I.
```

## 边界

- **不含断言**：生成时 `--default-layer-specialization=disable` 丢弃了 Chisel 的
  verification layer。`{parameters_doc['assertions']['chisel_assertions_in_firrtl']}`
  条 Chisel 断言存在于 FIRRTL，本包 SystemVerilog 中 `$fatal` 为
  `{parameters_doc['assertions']['systemverilog_fatal']}`。需要不变量检查时由 testbench 提供。
- **difftest 可选**：`DiffExt*.v` 由 `` `ifdef DIFFTEST `` 保护；不定义该宏时可独立编译，
  定义时需另供 `DifftestMacros.svh` 与 difftest C++ 库。
- 与上游 `make verilog` 的 RTL 内容相同，差别是缺少 Makefile 附加的提交注释头。
- 这份 RTL 是某个基线的完整硬件描述；任何模块级 UT 结论只属于对应运行记录，
  不是本包的属性。

逐文件校验和见 `SHA256SUMS`，许可证见 `LICENSE-MulanPSL2.txt`。
"""


def stage(project, baseline, destination, package):
    generation, record = generation_directory(project, baseline)
    rtl = generation / 'rtl'
    inventory = file_inventory(rtl)
    root = destination / package
    if root.exists():
        raise UcvError(f'Staging directory already exists: {root}')
    (root / 'rtl').mkdir(parents=True)
    for name in inventory['sv'] + inventory['v'] + ['filelist.f']:
        shutil.copy2(rtl / name, root / 'rtl' / name)
    licence = project.root / '.cache/sources' / _source_key(baseline) / 'LICENSE'
    if not licence.is_file():
        raise UcvError(f'Upstream licence not found at {licence}; run ucv prepare first')
    shutil.copy2(licence, root / 'LICENSE-MulanPSL2.txt')
    document = build_parameters(project, baseline, generation, record, inventory, package)
    (root / 'BUILD-PARAMETERS.json').write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + '\n')
    (root / 'README.md').write_text(readme(baseline, document, package))
    sums = []
    for path in sorted(p for p in root.rglob('*') if p.is_file()):
        sums.append(f'{file_hash(path)}  {path.relative_to(root).as_posix()}')
    (root / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
    return root, inventory, document


def _source_key(baseline):
    from ucv.sources import source_key
    return source_key(baseline)


def pack(root, archive):
    """Archive the staging tree reproducibly.

    ``tarfile.add`` embeds each file's mtime, uid, gid and owner, and gzip
    embeds its own timestamp, so re-running the script over identical content
    produced a different archive hash. Both are pinned here, and members are
    ordered explicitly because directory iteration order is filesystem
    dependent. Rebuilding an unchanged package then reproduces the published
    bytes.
    """
    if archive.exists():
        raise UcvError(f'Archive already exists: {archive}')
    root = Path(root)
    members = [root] + sorted(p for p in root.rglob('*'))
    with archive.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, compresslevel=9,
                           mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w') as stream:
                for path in members:
                    relative = root.name if path == root else f'{root.name}/{path.relative_to(root)}'
                    info = stream.gettarinfo(str(path), arcname=relative)
                    info.mtime = 0
                    info.uid = info.gid = 0
                    info.uname = info.gname = ''
                    info.mode = 0o755 if info.isdir() else 0o644
                    if info.isfile():
                        with path.open('rb') as handle:
                            stream.addfile(info, handle)
                    else:
                        stream.addfile(info)
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', help='named baseline, e.g. public-e716c7658')
    parser.add_argument('--output', default=None, help='directory for the staging tree and archive')
    parser.add_argument('--package', default=None, help='package name inside the archive')
    args = parser.parse_args()
    project = Project()
    baseline = project.baseline(args.baseline)
    package = args.package or f'xiangshan-{baseline["commit"][:9]}-rtl'
    output = Path(args.output) if args.output else project.root / '.cache' / 'release-staging'
    output.mkdir(parents=True, exist_ok=True)
    root, inventory, document = stage(project, baseline, output, package)
    archive = pack(root, output / f'{package}.tar.gz')
    print(json.dumps({
        'baseline': baseline['name'],
        'commit': baseline['commit'],
        'package': package,
        'staging': str(root),
        'archive': str(archive),
        'archive_sha256': file_hash(archive),
        'archive_bytes': archive.stat().st_size,
        'baseline_sha256': digest(baseline),
        'modules': len(inventory['sv']),
        'verilog': len(inventory['v']),
        'filelist_entries': len(inventory['entries']),
        'assertions_in_firrtl': document['assertions']['chisel_assertions_in_firrtl'],
        'fatal_in_systemverilog': document['assertions']['systemverilog_fatal'],
    }, indent=2))


if __name__ == '__main__':
    main()
