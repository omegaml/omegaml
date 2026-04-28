from importlib import import_module

from omegaml.client.cli.stores import StoresCommandMixin
from omegaml.client.docoptparser import CommandBase
from omegaml.client.util import get_omega


class ModelsCommandBase(StoresCommandMixin, CommandBase):
    """
    Usage:
      om models list [<pattern>] [--raw] [-E|--regexp] [options]
      om models get <name> <path>
      om models put <spec> <name>
      om models drop <name>
      om models metadata <name>

    Description:
        Work with models

    .. versionchanged:: 0.18.0
         om models put <spec> <name> now supports arbitrary model specifications

    .. versionchanged:: NEXT
        om models get <name> <path> is the same as om.models.get(name, local='<path>')
    """
    command = 'models'

    def get(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        path = self.args.get('<path>')
        result = om.models.get(name, local=path, replace=True)
        self.logger.info(result)

    def put(self):
        om = get_omega(self.args)
        spec = self.args.get('<spec>')
        name = self.args.get('<name>')
        try:
            modname, modelfn = spec.rsplit('.', maxsplit=1)
            mod = import_module(modname)
            modelfn = getattr(mod, modelfn)
            model = modelfn()
        except:
            # use
            model = spec
        result = om.models.put(model, name)
        self.logger.info(result)
