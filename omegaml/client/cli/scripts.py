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
        om scripts restart app <name> [options]

    Description:
        restart requires a login to omega-ml cloud
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

    def restart(self):
        import requests
        om = get_omega(self.args)
        name = self.args.get('<name>')
        user = om.runtime.auth.userid
        auth = requests.auth.HTTPBasicAuth(user, om.runtime.auth.apikey)
        url = om.defaults.OMEGA_RESTAPI_URL
        stop = requests.get(f'{url}/apps/api/stop/{user}/{name}'.format(om.runtime.auth.userid),
                            auth=auth)
        start = requests.get(f'{url}/apps/api/start/{user}/{name}'.format(om.runtime.auth.userid),
                             auth=auth)
        self.logger.info(f'stop: {stop} start: {start}')
