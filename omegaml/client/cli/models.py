from importlib import import_module

from omegaml.client.cli.stores import StoresCommandMixin
from omegaml.client.docoptparser import CommandBase
from omegaml.client.util import get_omega


class ModelsCommandBase(StoresCommandMixin, CommandBase):
    """
    Usage:
      om models list [<pattern>] [--raw] [-E|--regexp] [options]
      om models put <module.callable> <name>
      om models drop <name>
      om models metadata <name>

    Description:
        Work with models
    """
    command = 'models'

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





