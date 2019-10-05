from importlib import import_module

from omegaml.client.docoptparser import DocoptCommand
from omegaml.client.util import get_omega


class ModelsCommand(DocoptCommand):
    """
    Usage:
      om models put <module.callable> <name>
      om models list [<pattern>] [--raw]
      om models metadata <name>
    """
    command = 'models'

    def list(self):
        om = get_omega(self.args)
        pattern = self.args.get('<pattern>')
        raw = self.args.get('--raw')
        self.logger.info(om.models.list(pattern=pattern, raw=raw))

    def put(self):
        om = get_omega(self.args)
        modname = self.args.get('<module.callable>')
        name = self.args.get('<name>')
        modname, modelfn = modname.rsplit('.', maxsplit=1)
        try:
            mod = import_module(modname)
        except:
            raise
        modelfn = getattr(mod, modelfn)
        model = modelfn()
        self.logger.info(om.models.put(model, name))

    def metadata(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        self.logger.info(om.models.metadata(name).to_json())




