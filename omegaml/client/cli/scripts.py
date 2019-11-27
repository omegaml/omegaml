import os

from omegaml.client.docoptparser import DocoptCommand
from omegaml.client.util import get_omega


class ScriptsCommand(DocoptCommand):
    """
    Usage:
        om scripts list [<pattern>] [options]
        om scripts put <path> <name> [options]
    """
    command = 'scripts'

    def list(self):
        om = get_omega(self.args)
        raw = self.args.get('--raw', False)
        print(om.scripts.list(raw=raw))

    def put(self):
        om = get_omega(self.args)
        script_path = self.args.get('<path>')
        name = self.args.get('<name>')
        if os.path.exists(script_path):
            name = name or os.path.basename(script_path)
            abs_path = os.path.abspath(script_path)
            meta = om.scripts.put('pkg://{}'.format(abs_path), name)
            print(meta)
        else:
            raise ValueError('{} is not a valid path'.format(script_path))

        
