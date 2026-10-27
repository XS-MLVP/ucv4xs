"""The ucv command. SPDX-License-Identifier: MPL-2.0."""
import argparse
import json
from pathlib import Path
import platform
import shutil
import sys
from .common import UcvError, execute, read
from .config import Project

def main(argv=None):
    parser=argparse.ArgumentParser(prog='ucv')
    parser.add_argument('--root',type=Path)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('list','doctor','prepare','build','run'):
        p=sub.add_parser(name)
        p.add_argument('selection',nargs='*',help='suite, group, public (default), or full')
        p.add_argument('--require-unified-baseline',action='store_true')
        if name in {'list','doctor'}:p.add_argument('--json',action='store_true')
        if name in {'prepare','build'}:
            p.add_argument('--dut',action='append')
            p.add_argument('--jobs',type=int,default=16)
        if name=='run':
            p.add_argument('--workers',type=int,default=8)
            p.add_argument('--seed',type=int,default=1)
            p.add_argument('--collect-only',action='store_true')
            p.add_argument('--output',type=Path)
    p=sub.add_parser('setup');p.add_argument('--jobs',type=int,default=16)
    p=sub.add_parser('report');p.add_argument('directory',type=Path,nargs='?');p.add_argument('--compare',type=Path)
    raw=list(sys.argv[1:] if argv is None else argv)
    forwarded=[]
    if '--' in raw:
        index=raw.index('--');raw,forwarded=raw[:index],raw[index+1:]
    args=parser.parse_args(raw)
    try:
        project=Project(args.root)
        if forwarded and args.command!='run':raise UcvError('Only ucv run accepts pytest arguments after --')
        if args.command=='setup':
            from .setup import setup
            if args.jobs<1:raise UcvError('jobs must be positive')
            print(setup(project,args.jobs));return 0
        if args.command=='report':
            from .report import report
            path=args.directory or Path(read(project.root/'.ucv/last-run.json')['path'])
            result=report(path,args.compare)
            print(json.dumps({k:v for k,v in result.items() if k not in {'cases','coverage_reports'}},ensure_ascii=False,indent=2))
            return 0 if result['hardware_verdict']=='PASS' else 1
        suites=project.select(args.selection,args.require_unified_baseline)
        if args.command in {'list','doctor'}:
            result={'suites':[s.summary() for s in suites],
                    'mixed_baseline':len({s.baseline_key for s in suites})>1}
            errors=[]
            if args.command=='doctor':
                if sys.version_info[:2]!=(3,12):errors.append('Python 3.12 required')
                if (platform.system(),platform.machine())!=('Linux','x86_64'):errors.append('Linux x86_64 required')
                for tool in ('git','java','cmake','g++','swig','make'):
                    if not shutil.which(tool):errors.append('Missing host tool: '+tool)
                for file in ('.venv/bin/python','.tools/bin/picker','.tools/bin/mill','.tools/bin/firtool','.tools/verilator/bin/verilator'):
                    if not (project.root/file).is_file():errors.append('Missing project tool: '+file)
                for suite in suites:
                    if suite.baseline['visibility']=='internal':
                        path=project.local.get('source_mirrors',{}).get(suite.baseline['name'])
                        if not path or not Path(path).is_dir():errors.append('Missing external source: '+suite.name)
                result['errors']=errors
            if args.json:print(json.dumps(result,ensure_ascii=False,indent=2))
            else:
                for s in suites:print(f"{s.name:9} {len(s.recipe['duts']):2} DUTs  {s.baseline['commit'][:12]}  {s.inherited_from}")
                print('MIXED BASELINES' if result['mixed_baseline'] else 'UNIFIED BASELINE')
                for error in errors:print('ERROR: '+error)
            return int(bool(errors))
        if args.command in {'prepare','build'}:
            from .build import build_many
            if args.jobs<1:raise UcvError('jobs must be positive')
            results=build_many(project,suites,args.dut,args.jobs,args.command=='prepare')
            return int(any(r['status']!='PASS' for r in results))
        from .run import run
        from .report import report
        output,result=run(project,suites,args.workers,args.seed,forwarded,args.collect_only,args.output)
        report(output)
        print(output)
        return int(result['status']!='PASS')
    except (UcvError,OSError,ValueError,KeyError) as error:
        print(f'ucv: {error}',file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
