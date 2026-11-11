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
    for name in ('list','info','check','docs','doctor','prepare','build','run'):
        p=sub.add_parser(name)
        p.add_argument('selection',nargs='*',help='suite, group, public (default), or full')
        p.add_argument('--require-unified-baseline',action='store_true')
        if name in {'list','info','check','docs','doctor'}:p.add_argument('--json',action='store_true')
        if name=='docs':p.add_argument('--write',action='store_true',help='refresh generated bug indexes and testbench work entrances')
        if name in {'info','prepare','build','run'}:p.add_argument('--dut',action='append')
        if name=='doctor':p.add_argument('--stage',choices=('source','rtl','run','generate'),default='run')
        if name in {'prepare','build'}:
            p.add_argument('--jobs',type=int,default=16)
            p.add_argument('--rtl-source',choices=('auto','release','source'),default='auto',
                           help='auto: verified local generation or pinned release; never silently generate')
            p.add_argument('--archive',type=Path,help='offline copy of the pinned release archive')
        if name=='prepare':p.add_argument('--source-only',action='store_true')
        if name=='run':
            p.add_argument('--workers',type=int,default=8)
            p.add_argument('--seed',type=int,default=1)
            p.add_argument('--collect-only',action='store_true')
            p.add_argument('--output',type=Path)
    p=sub.add_parser('setup');p.add_argument('--jobs',type=int,default=16)
    p.add_argument('--profile',choices=('runtime','full'),default='runtime')
    p=sub.add_parser('init')
    p.add_argument('suite');p.add_argument('--group',required=True);p.add_argument('--dut',required=True)
    p.add_argument('--top',required=True);p.add_argument('--export-name',required=True)
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
            print(setup(project,args.jobs,args.profile));return 0
        if args.command=='init':
            from .workspace import initialize
            print(initialize(project,args.suite,args.group,args.dut,args.top,args.export_name));return 0
        if args.command=='report':
            from .report import report
            path=args.directory or Path(read(project.root/'.ucv/last-run.json')['path'])
            result=report(path,args.compare)
            print(json.dumps({k:v for k,v in result.items() if k not in {'cases','coverage_reports','coverage_artifacts'}},ensure_ascii=False,indent=2))
            return 0 if result['hardware_verdict'] in {'PASS','UNCERTAIN'} else 1
        suites=project.select(args.selection,args.require_unified_baseline)
        if args.command=='docs':
            from .documents import refresh_index
            from .layout import layout_names, refresh_readmes
            from .workspace import metadata
            values=[refresh_index(project,s,args.write) for s in suites]
            for suite,row in zip(suites,values):
                meta=metadata(suite)
                directory,_=layout_names(meta)
                row[directory]=refresh_readmes(project,suite,meta,args.write)
                row['updated']=row['updated'] or any(p['updated'] for p in row[directory])
            if args.json:print(json.dumps([{k:v for k,v in row.items() if k!='markdown'} for row in values],ensure_ascii=False,indent=2))
            elif args.write:
                for row in values:print(f"{row['suite']}: {'UPDATED' if row['updated'] else 'CURRENT'} {row['path']}")
            else:
                for row in values:print(f"# {row['suite']}\n\n{row['markdown']}")
            return 0
        if args.command=='info':
            from .workspace import info, markdown
            values=[info(project,s,args.dut) for s in suites]
            print(json.dumps(values,ensure_ascii=False,indent=2) if args.json else '\n'.join(markdown(v) for v in values))
            return 0
        if args.command=='check':
            from .workspace import check
            result=check(project,suites)
            if args.json:print(json.dumps(result,ensure_ascii=False,indent=2))
            else:
                print(result['status']+' (structure-only)')
                for message in result['errors']:print('ERROR: '+message)
                for message in result['notices']:print('INFO: '+message)
                for row in result['documents']:
                    print(f"{row['root']}: {len(row['current'])} current pages; {len(row['unindexed'])} other documents (not deletion candidates; --json lists them)")
            return int(bool(result['errors']))
        if args.command in {'list','doctor'}:
            result={'suites':[s.summary() for s in suites],
                    'mixed_baseline':len({s.baseline_key for s in suites})>1}
            errors=[]
            if args.command=='doctor':
                if sys.version_info[:2]!=(3,12):errors.append('Python 3.12 required')
                native=args.stage in {'run','generate'}
                if native and (platform.system(),platform.machine())!=('Linux','x86_64'):errors.append('Linux x86_64 required')
                host={'source':('git',),'rtl':(),'run':('git','cmake','g++','swig','make'),
                      'generate':('git','java','cmake','g++','swig','make')}[args.stage]
                for tool in host:
                    if not shutil.which(tool):errors.append('Missing host tool: '+tool)
                files=['.venv/bin/python','.tools/bin/picker','.tools/verilator/bin/verilator'] if native else []
                if args.stage=='generate':files+=['.tools/bin/mill','.tools/bin/firtool']
                for file in files:
                    if not (project.root/file).is_file():errors.append('Missing project tool: '+file)
                for suite in suites:
                    if suite.baseline['visibility']=='internal':
                        path=project.local.get('source_mirrors',{}).get(suite.baseline['name'])
                        if not path or not Path(path).is_dir():errors.append('Missing external source: '+suite.name)
                if args.stage=='rtl':
                    from .releases import release_spec
                    for suite in suites:
                        try:release_spec(project,suite.baseline)
                        except UcvError as error:errors.append(str(error))
                if not errors and native:
                    from .validation import installed_tools
                    try:installed_tools(project,generation=args.stage=='generate')
                    except (UcvError,OSError) as error:errors.append(str(error))
                result['errors']=errors
            if args.json:print(json.dumps(result,ensure_ascii=False,indent=2))
            else:
                for s in suites:print(f"{s.name:9} {len(s.recipe['duts']):2} DUTs  {s.baseline['commit'][:12]}  {s.baseline['design']['config']}  {s.baseline['name']} <- {s.inherited_from}")
                print('MIXED BASELINES' if result['mixed_baseline'] else 'UNIFIED BASELINE')
                for error in errors:print('ERROR: '+error)
            return int(bool(errors))
        if args.command in {'prepare','build'}:
            from .build import build_many
            if args.jobs<1:raise UcvError('jobs must be positive')
            if args.archive and args.rtl_source!='release':raise UcvError('--archive requires --rtl-source release')
            if args.command=='prepare' and args.source_only:
                if args.archive or args.rtl_source!='auto':raise UcvError('--source-only cannot select an RTL source')
                from .sources import source
                from .common import activate, lock
                from .workspace import selected_duts
                for suite in suites:
                    selected_duts(suite,args.dut)
                    with lock(project.root/'.cache/locks'/('suite-run-'+suite.name)):
                        checkout=source(project,suite.baseline)
                        activate(suite.path/'XiangShan',checkout)
                        print(f'{suite.name}: SOURCE {checkout}')
                return 0
            results=build_many(project,suites,args.dut,args.jobs,args.command=='prepare',args.rtl_source,args.archive)
            return int(any(r['status']!='PASS' for r in results))
        from .run import run
        from .report import report
        output,result=run(project,suites,args.workers,args.seed,forwarded,args.collect_only,args.output,args.dut)
        summary=report(output)
        print(output)
        print(f"run_status={result['status']} hardware_verdict={summary['hardware_verdict']} "
              f"counts={summary.get('counts',{})}")
        for gap in summary.get('gaps',[]):print('GAP: '+gap)
        return int(result['status'] not in {'PASS','UNCERTAIN'} or
                   summary['hardware_verdict'] not in {'PASS','UNCERTAIN'})
    except (UcvError,OSError,ValueError,KeyError) as error:
        print(f'ucv: {error}',file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
