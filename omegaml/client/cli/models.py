from importlib import import_module

from omegaml.client.docoptparser import CommandBase
from omegaml.client.util import get_omega


class ModelsCommandBase(CommandBase):
    """
    Usage:
      om models put <module.callable> <name>
      om models drop <name>
      om models list [<pattern>] [--raw] [-E|--regexp] [options]
      om models metadata <name>

    Description:
        Great stuff with models
    """
    command = 'models'

    def list(self):
        om = get_omega(self.args)
        pattern = self.args.get('<pattern>')
        regexp = self.args.get('--regexp') or self.args.get('-E')
        raw = self.args.get('--raw')
        kwargs = dict(regexp=pattern) if regexp else dict(pattern=pattern)
        self.logger.info(om.models.list(raw=raw, **kwargs))

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

    def drop(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        self.logger.info(om.models.drop(name))

    def metadata(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        self.logger.info(om.models.metadata(name).to_json())




