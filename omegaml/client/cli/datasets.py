import imghdr

import pandas as pd

from omegaml.client.docoptparser import CommandBase
from omegaml.client.util import get_omega


class DatasetsCommandBase(CommandBase):
    """
    Usage:
      om datasets list [<pattern>] [--raw] [-E|--regexp] [options]
      om datasets put <path> <name> [--replace] [--csv=<param=value>]... [options]
      om datasets get <name> <path> [--csv <param>=<value>]... [options]
      om datasets drop <name> [--force] [options]
      om datasets metadata <name> [options]

    Options:
      --raw   return metadata

    Description:
         For csv files, put and get accept the --csv option multiple times.
         The <param>=<value> pairs will be used as kwargs to pd.read_csv (on put)
         and df.to_csv methods (on get)
    """
    command = 'datasets'

    def list(self):
        om = get_omega(self.args)
        raw = self.args.get('--raw', False)
        regexp = self.args.get('--regexp') or self.args.get('-E')
        pattern = self.args.get('<pattern>')
        kwargs = dict(regexp=pattern) if regexp else dict(pattern=pattern)
        entries = om.datasets.list(raw=raw, **kwargs)
        self.logger.info(entries)

    def put(self):
        om = get_omega(self.args)
        local = self.args['<path>']
        name = self.args['<name>']
        replace = self.args['--replace']
        csvkwargs = self.parse_kwargs('--csv')
        # TODO introduce a puggable filetype processing backend to do this
        if local.endswith('.csv'):
            # csv formats
            import pandas as pd
            data = pd.read_csv(local, **csvkwargs)
            meta = om.datasets.put(data, name, append=not replace)
        elif imghdr.what(local):
            # images
            from imageio import imread
            img = imread(local)
            meta = om.datasets.put(img, name)
        else:
            meta = om.datasets.put(local, name, append=not replace)
        self.logger.info(meta)

    def load(self):
        return self.put()

    def export(self):
        return self.get()

    def get(self):
        om = get_omega(self.args)
        local = self.args['<path>']
        name = self.args['<name>']
        obj = om.datasets.get(name)
        csvkwargs = self.parse_kwargs('--csv', index=False)
        if isinstance(obj, pd.DataFrame):
            obj.to_csv(local, **csvkwargs)
        elif hasattr(obj, 'read'):
            with open(local, 'wb') as fout:
                while True:
                    data = obj.read(1024 * 10)
                    if not data:
                        break
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
