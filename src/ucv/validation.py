"""Validate the installed tools before accepting their outputs. MPL-2.0."""
import json
import os
from . import host
from .common import UcvError, execute, file_hash, read

def installed_tools(project, runtime=True, generation=False):
    if not (project.root/'.tools/receipt.json').is_file():
        raise UcvError('Project tools are not installed; run ucv setup')
    receipt=read(project.root/'.tools/receipt.json')
    if receipt['tools']!=project.tools:
        raise UcvError('Installed tool lock differs from dependencies/versions.json; run ucv setup')
    # Every installed binary and native library is architecture-specific, and
    # identical bytes on another machine still cannot run here.
    installed_machine = receipt.get('machine')
    if installed_machine is None:
        raise UcvError('Installed tool receipt does not record the host architecture; run ucv setup')
    if installed_machine != host.machine():
        raise UcvError(f'Installed tools were built for {installed_machine} but this host is '
                       f'{host.machine()}; run ucv setup here')
    if receipt.get('system') != host.system():
        raise UcvError(f'Installed tools were built for {receipt.get("system", "an unknown system")} '
                       f'but this host is {host.system()}; run ucv setup here')
    names=['bin/picker','verilator/bin/verilator_bin']
    if generation:names+=['bin/mill','bin/firtool']
    for name in names:
        expected=receipt['binaries'].get(name)
        if not expected:
            raise UcvError('Missing installed tool receipt: '+name+'; run ucv setup --profile full for generation')
        if file_hash(project.root/'.tools'/name)!=expected:
            raise UcvError('Installed tool content changed: '+name)
    if runtime:
        env=project.environment()
        env['PYTHONPATH']=str(project.root/'src')+os.pathsep+env.get('PYTHONPATH','')
        result=execute([project.runtime_python(),'-c',
                        'import json; from ucv.runtime import validate_runtime; '
                        'print(json.dumps(validate_runtime()))'],cwd=project.root,env=env)
        # The build tool receipt stays untouched.  Record the actual selected
        # runtime separately, especially when testing an uncommitted Toffee.
        receipt={**receipt,'runtime':json.loads(result.stdout)}
    return receipt
