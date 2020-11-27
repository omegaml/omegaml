import os

from omegaml.backends.package import PythonPipSourcedPackageData
from omegaml.client.docoptparser import CommandBase
from omegaml.client.util import get_omega


class ScriptsCommandBase(CommandBase):
    """
    Usage:
        om scripts list [<pattern>] [options]
        om scripts put <path> <name> [options]
        om scripts drop <name> [options]

    Description:
    """
    command = 'scripts'

    def list(self):
        om = get_omega(self.args)
        raw = self.args.get('--raw', False)
        self.logger.info(om.scripts.list(raw=raw))

    def put(self):
        om = get_omega(self.args)
        script_path = self.args.get('<path>')
        name = self.args.get('<name>')
        as_pypi = lambda v: 'pypi://{}'.format(v)
        if os.path.exists(script_path):
            name = name or os.path.basename(script_path)
            abs_path = os.path.abspath(script_path)
            meta = om.scripts.put('pkg://{}'.format(abs_path), name)
        elif PythonPipSourcedPackageData.supports(script_path, name):
            meta = om.scripts.put(script_path, name)
        elif PythonPipSourcedPackageData.supports(as_pypi(script_path), name):
            meta = om.scripts.put(as_pypi(script_path), name)
        else:
            raise ValueError('{} is not a valid path'.format(script_path))
        self.logger.info(meta)

    def drop(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        om.scripts.drop(name, force=True)

