from omegaml.client.docoptparser import DocoptCommand
from omegaml.client.util import get_omega


class DatasetsCommand(DocoptCommand):
    """
    Usage:
      om datasets list [<pattern>] [--raw]
      om datasets put <path> <name> [--replace]
      om datasets get <name> <path>
      om datasets drop <name> [--force]
      om datasets metadata <name>
    """
    command = 'datasets'

    def list(self):
        om = get_omega(self.args)
        raw = self.args.get('--raw', False)
        pattern = self.args.get('<pattern>')
        entries = om.datasets.list(pattern=pattern, raw=raw)
        self.logger.info(entries)

    def put(self):
        om = get_omega(self.args)
        local = self.args['<path>']
        name = self.args['<name>']
        replace = self.args['--replace']
        if local.endswith('.csv'):
            import pandas as pd
            data = pd.read_csv(local)
            self.logger.info(om.datasets.put(data, name, append=not replace))
        else:
            self.logger.info(om.datasets.put(local, name, append=not replace))

    def get(self):
        om = get_omega(self.args)
        local = self.args['<path>']
        name = self.args['<name>']
        data = om.datasets.get(name).read()
        with open(local, 'wb') as fout:
            fout.write(data)
        self.logger.debug(local)

    def drop(self):
        om = get_omega(self.args)
        name = self.args['<name>']
        force = self.args['--force']
        om.datasets.drop(name, force=force)

    def metadata(self):
        om = get_omega(self.args)
        name = self.args.get('<name>')
        self.logger.info(om.datasets.metadata(name).to_json())

    def plugins(self):
        om = get_omega(self.args)
        for kind, plugincls in om.defaults.OMEGA_STORE_BACKENDS.items():
            self.logger.info(kind, plugincls.__doc__)
