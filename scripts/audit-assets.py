#!/usr/bin/env python3
"""Check the public source boundary without requiring native tools. MPL-2.0."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from ucv.config import Project
from ucv.common import UcvError


def audit(root):
    root = Path(root).resolve()
    project = Project(root)
    suites = project.select(['full'])
    listed = subprocess.check_output(['git','-C',str(root),'ls-files','-z','--cached','--others','--exclude-standard'])
    files = sorted(set(listed.decode().split('\0'))-{''})
    errors = []
    forbidden_dirs = {'.venv','.tools','.cache','.ucv','.history','results','rtl','dut','XiangShan','XiangShan-internal'}
    forbidden_suffixes = {'.so','.a','.o','.fst','.vcd','.dat','.fir','.v','.sv','.vh','.svh','.pyc'}
    for name in files:
        path = root/name
        if not path.exists() and not path.is_symlink():continue  # pending source deletion
        if forbidden_dirs.intersection(Path(name).parts) or path.suffix in forbidden_suffixes or '.so.' in path.name:
            errors.append('Generated/external asset is publishable: '+name)
        if path.is_symlink():errors.append('Source checkout depends on a symlink: '+name)
        if path.is_file() and path.suffix=='.py':
            try:tree=ast.parse(path.read_text(),filename=name)
            except (SyntaxError,UnicodeError) as error:errors.append(str(error));continue
            for node in ast.walk(tree):
                modules=([node.module] if isinstance(node,ast.ImportFrom) else
                         [alias.name for alias in node.names] if isinstance(node,ast.Import) else [])
                if any(m and m.split('.')[0] in {'xreactor','xsverify'} for m in modules):
                    errors.append('Legacy runtime import: '+name)
    index = json.loads((root/'docs/history/evidence-index.json').read_text())
    total = 0
    for shard in index['shards']:
        path=root/'docs/history'/shard['path']
        content=path.read_bytes()
        if hashlib.sha256(content).hexdigest()!=shard['sha256']:errors.append('Evidence index hash changed: '+str(path))
        rows=[json.loads(line) for line in content.decode().splitlines()]
        if len(rows)!=shard['entries'] or any(row['suite']!=shard['suite'] or not row['source'].startswith('history://'+shard['suite']+'/') for row in rows):
            errors.append('Evidence shard identity/count mismatch: '+shard['suite'])
        total+=len(rows)
    if total!=index['entries']:errors.append('Evidence index total mismatch')
    for suite in suites:
        for name in ('pytest.ini','README.md','ucv.json'):
            if not (suite.path/name).is_file():errors.append(f'{suite.name}: missing {name}')
        if not (suite.path/'tests').is_dir():errors.append(f'{suite.name}: missing test root')
    return {'status':'FAIL' if errors else 'PASS','source_files':len(files),
            'suites':len(suites),'duts':sum(len(s.recipe['duts']) for s in suites),
            'historical_evidence_entries':total,'errors':errors}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:result=audit(ROOT)
    except (OSError,ValueError,KeyError,UcvError) as error:result={'status':'FAIL','errors':[str(error)]}
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text)
    print(text,end='')
    raise SystemExit(result['status']!='PASS')
