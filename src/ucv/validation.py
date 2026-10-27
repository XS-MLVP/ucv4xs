"""Validate the installed tools before accepting their outputs. MPL-2.0."""
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
        execute([project.root/'.venv/bin/python','-c',
                 'from ucv.runtime import validate_runtime; validate_runtime()'],
                cwd=project.root,env=project.environment())
    return receipt
