"""Validated whole-suite baseline inheritance. SPDX-License-Identifier: MPL-2.0."""
from dataclasses import dataclass
import os
from pathlib import Path
import re
from .common import UcvError, contained, digest, file_hash, read

HEX = re.compile(r'[0-9a-f]{40}\Z')

@dataclass(frozen=True)
class Suite:
    name: str
    path: Path
    recipe: dict
    baseline: dict
    inherited_from: str

    @property
    def baseline_key(self):
        return digest({k:v for k,v in self.baseline.items() if k != 'name'})

    def summary(self):
        return {'suite':self.name, 'baseline':self.baseline['name'],
                'commit':self.baseline['commit'], 'inherited_from':self.inherited_from,
                'design_config':self.baseline['design']['config'], 'group':self.path.parent.name,
                'visibility':self.baseline['visibility'],
                'baseline_fingerprint':self.baseline_key, 'duts':list(self.recipe['duts'])}

class Project:
    def __init__(self, root=None):
        if root is None:
            start = Path(os.environ.get('UCV_ROOT', Path.cwd())).resolve()
            candidates = [start, *start.parents, Path(__file__).resolve().parents[2]]
            root = next((p for p in candidates if (p/'ucv.json').is_file() and 'suites' in read(p/'ucv.json')), None)
        if root is None:
            raise UcvError('Cannot locate ucv.json; run from the repository or use --root')
        self.root = Path(root).resolve()
        self.config = read(self.root/'ucv.json')
        self.local = read(self.root/'.ucv/local.json') if (self.root/'.ucv/local.json').exists() else {}
        self.tools = read(self.root/'dependencies/versions.json')

    def baseline(self, name):
        if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+', name):
            raise UcvError(f'Invalid baseline reference: {name!r}')
        data = read(self.root/'baselines'/f'{name}.json')
        required = {'repository','commit','recursive_submodules','design','patches','tools','firtool_options','visibility'}
        if required - data.keys() or data.get('name') != name:
            raise UcvError(f'Incomplete baseline {name}: missing {sorted(required-data.keys())}')
        if not isinstance(data['commit'],str) or not HEX.fullmatch(data['commit']) or not isinstance(data['repository'],str) or not data['repository']:
            raise UcvError(f'{name}: a complete repository and 40-character commit are required')
        design, tools = data['design'], data['tools']
        if (not isinstance(design,dict) or not isinstance(tools,dict)
                or not {'config','num_cores','top'} <= design.keys()
                or not {'mill','chisel','firtool','java'} <= tools.keys()):
            raise UcvError(f'{name}: incomplete design/tool versions')
        if (any(not isinstance(design[k],str) or not design[k] for k in ('config','top'))
                or type(design['num_cores']) is not int or design['num_cores'] < 1):
            raise UcvError(f'{name}: incomplete design configuration')
        if not all(isinstance(x, str) and x for x in tools.values()):
            raise UcvError(f'{name}: tool versions must be explicit')
        if data['visibility'] not in {'public','internal'}:
            raise UcvError(f'{name}: visibility must be public or internal')
        for label, values in (('firtool_options',data['firtool_options']),
                              ('chisel_args',design.get('chisel_args',[]))):
            if not isinstance(values,list) or any(not isinstance(v,str) or not v for v in values):
                raise UcvError(f'{name}: {label} must be a list of explicit arguments')
        if not isinstance(data['recursive_submodules'],list) or not isinstance(data['patches'],list):
            raise UcvError(f'{name}: submodule and patch locks must be lists')
        seen = set()
        for entry in data['recursive_submodules']:
            if (not isinstance(entry,dict) or set(entry) != {'path','repository','commit'}
                    or not isinstance(entry['commit'],str) or not HEX.fullmatch(entry['commit'])
                    or not isinstance(entry['path'],str) or entry['path'] in {'','.','..'}):
                raise UcvError(f'{name}: incomplete recursive submodule lock')
            contained(self.root, entry['path'])
            if entry['path'] in seen or not entry['repository']:
                raise UcvError(f'{name}: duplicate/invalid submodule')
            seen.add(entry['path'])
        for patch in data['patches']:
            if not isinstance(patch,dict) or set(patch) != {'path','sha256'} or file_hash(contained(self.root, patch['path'])) != patch['sha256']:
                raise UcvError(f'{name}: patch hash mismatch')
        return data

    def suite(self, name):
        if name not in self.config['suites']:
            raise UcvError(f'Unknown suite: {name}')
        path = contained(self.root, self.config['suites'][name])
        selected = None
        origin = None
        chain = [self.root] + [self.root.joinpath(*path.relative_to(self.root).parts[:i])
                                for i in range(1, len(path.relative_to(self.root).parts)+1)]
        for directory in chain:
            file = directory/'ucv.json'
            if file.exists():
                config = read(file)
                if 'baseline' in config:
                    selected = self.baseline(config['baseline'])
                    origin = str(file.relative_to(self.root))
        if selected is None:
            raise UcvError(f'{name}: no inherited baseline')
        recipe = read(path/'ucv.json')
        if not recipe.get('duts') or recipe.get('suite') != name:
            raise UcvError(f'{name}: missing DUT recipe')
        if recipe.get('generation') not in {'soc','bpu-standalone'} or recipe.get('closure','module-dependencies') != 'module-dependencies':
            raise UcvError(f'{name}: unsupported generation or closure recipe')
        for key, spec in recipe['duts'].items():
            if not re.fullmatch(r'\w+', key) or not {'top','export_name'} <= spec.keys():
                raise UcvError(f'{name}/{key}: incomplete DUT recipe')
            if {'baseline','commit','repository','patches','design','config','tools','firtool_options','recursive_submodules'} & spec.keys():
                raise UcvError(f'{name}/{key}: per-DUT baseline overrides are not supported')
        return Suite(name, path, recipe, selected, origin)

    def select(self, names=None, unified=False):
        selected = []
        for name in names or ['public']:
            if name in self.config['profiles']:
                selected.extend(self.config['profiles'][name])
            elif name in self.config['suites']:
                selected.append(name)
            else:
                group = [k for k,v in self.config['suites'].items() if Path(v).parent.name == name]
                if not group:
                    raise UcvError(f'Unknown suite/group/profile: {name}')
                selected.extend(group)
        suites = [self.suite(k) for k in dict.fromkeys(selected)]
        if unified and len({s.baseline_key for s in suites}) > 1:
            raise UcvError('Mixed baselines rejected before execution: ' + ', '.join(s.name+'='+s.baseline['name'] for s in suites))
        return suites

    def cache_key(self, suite, dut, options=None):
        overlay = self.root/'recipes/bpu/BpuVerifyMain.scala'
        return digest({'baseline':suite.baseline_key, 'suite':suite.name, 'dut':dut,
                       'recipe':suite.recipe, 'tools':self.tools, 'options':options or {},
                       'pipeline_version':1,
                       'build_options':self.config.get('build_options',{}),
                       'overlay':file_hash(overlay) if suite.recipe['generation']=='bpu-standalone' else None})

    def environment(self):
        env = dict(os.environ)
        prefix = self.root/'.tools'
        env.update(UCV_ROOT=str(self.root), PYTHONNOUSERSITE='1',
                   PATH=f'{self.root}/.venv/bin:{prefix}/bin:{prefix}/verilator/bin:'+env.get('PATH',''),
                   VERILATOR_ROOT=str(prefix/'verilator/share/verilator'))
        return env
