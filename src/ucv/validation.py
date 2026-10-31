"""Validate the installed tools before accepting their outputs. MPL-2.0."""
import json
import os
from .common import UcvError, execute, file_hash, read

def installed_tools(project, runtime=True):
    if not (project.root/'.tools/receipt.json').is_file():
        raise UcvError('Project tools are not installed; run ucv setup')
    receipt=read(project.root/'.tools/receipt.json')
    if receipt['tools']!=project.tools:
        raise UcvError('Installed tool lock differs from dependencies/versions.json; run ucv setup')
    for name,expected in receipt['binaries'].items():
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
