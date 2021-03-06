import imghdr
import pandas as pd

from omegaml.client.cli.stores import StoresCommandMixin
from omegaml.client.docoptparser import CommandBase
from omegaml.client.util import get_omega


class DatasetsCommandBase(StoresCommandMixin, CommandBase):
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

