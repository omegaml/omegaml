import os

from omegaml.backends.package import PythonPipSourcedPackageData
from omegaml.client.cli.stores import StoresCommandMixin
from omegaml.client.docoptparser import CommandBase
from omegaml.client.util import get_omega


class ScriptsCommandBase(StoresCommandMixin, CommandBase):
    """
    Usage:
        om scripts list [<pattern>] [--raw] [--hidden] [-E|--regexp] [options]
        om scripts put <path> <name> [options]
        om scripts get <name> [<local>] [--noinstall] [options]
        om scripts drop <name> [options]
        om scripts metadata <name> [options]

    Options:
        --hidden        list hidden entries
        --noinstall     do not install the package

    Description:
        Work with scripts
    """

    command = 'scripts'

    def put(self):
        om = get_omega(self.args)
        script_path = self.args.get('<path>')
        name = self.args.get('<name>')
        as_pypi = lambda v: f'pypi://{v}'
        if os.path.exists(script_path):
            name = name or os.path.basename(script_path)
            abs_path = os.path.abspath(script_path)
            meta = om.scripts.put(f'pkg://{abs_path}', name)
        elif PythonPipSourcedPackageData.supports(script_path, name):
            meta = om.scripts.put(script_path, name)
        elif PythonPipSourcedPackageData.supports(as_pypi(script_path), name):
            meta = om.scripts.put(as_pypi(script_path), name)
        else:
            raise ValueError(f'{script_path} is not a valid path')
        self.logger.info(meta)

    def get(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        localpath = self.args.get('<local>')
        noinstall = self.args.get('--noinstall')
        print(om.scripts.get(name, localpath=localpath, install=not noinstall))
