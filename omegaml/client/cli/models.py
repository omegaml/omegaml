from importlib import import_module

from omegaml.client.cli.stores import StoresCommandMixin
from omegaml.client.docoptparser import CommandBase
from omegaml.client.util import get_omega


class ModelsCommandBase(StoresCommandMixin, CommandBase):
    """
    Usage:
      om models list [<pattern>] [--raw] [-E|--regexp] [options]
      om models put <spec> <name>
      om models drop <name>
      om models metadata <name>

    Description:
        Work with models

    .. versionchanged:: 0.18.0
         om models put <spec> <name> now supports arbitrary model specifications
    """
    command = 'models'

    def put(self):
        om = get_omega(self.args)
        modname = self.args.get('<spec>')
        name = self.args.get('<name>')
        try:
            modname, modelfn = modname.rsplit('.', maxsplit=1)
            mod = import_module(modname)
            modelfn = getattr(mod, modelfn)
            model = modelfn()
        except:
            model = modname
        self.logger.info(om.models.put(model, name))
