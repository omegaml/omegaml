import smart_open

from omegaml.client.cli.stores import StoresCommandMixin
from omegaml.client.docoptparser import CommandBase
from omegaml.client.util import get_omega


class DatasetsCommandBase(StoresCommandMixin, CommandBase):
    """
    Usage:
      om datasets list [<pattern>] [--raw] [-E|--regexp] [options]
      om datasets put <path> <name> [--replace] [--csv=<param=value>]... [--format csv|image|binary] [options]
      om datasets get <name> <path> [--csv <param>=<value>]... [--format csv|binary] [options]
      om datasets drop <name> [--force] [options]
      om datasets metadata <name> [options]

    Options:
      --raw           return metadata
      --format VALUE  force the format of the file

    Description:
         For csv files, put and get accept the --csv option multiple times.
         The <param>=<value> pairs will be used as kwargs to pd.read_csv (on put)
         and df.to_csv methods (on get). Note that put uses read_csv because
         it must read the csv first, then store in om.datasets. Respectively,
         get uses to_csv because it must store the file locally.
    """
    command = 'datasets'

    def put(self):
        om = get_omega(self.args)
        local = self.args['<path>']
        name = self.args['<name>']
        replace = self.args['--replace']
        csvkwargs = self.parse_kwargs('--csv')
        # TODO introduce a puggable filetype processing backend to do this
        is_csv = self.args.get('--format') == 'csv' or anyext(local, '.csv')
        is_image = self.args.get('--format') == 'image' or anyext(local,
                                                                  '.png,.img,.bmp,.jpeg,.jpg,.tif,.tiff,.eps,.raw,.gif')
        is_binary = self.args.get('--format') == 'binary' or not (is_csv or is_image)
        if is_csv:
            # csv formats
            om.datasets.read_csv(local, name, append=not replace, **csvkwargs)
            meta = om.datasets.metadata(name)
        elif is_image:
            # images
            from imageio import imread
            with smart_open.open(local, 'rb') as fin:
                img = imread(fin)
                meta = om.datasets.put(img, name)
        elif is_binary:
            with smart_open.open(local, 'rb') as fin:
                meta = om.datasets.put(fin, name, append=not replace)
        else:
            meta = om.datasets.put(local, name, append=not replace)
        self.logger.info(meta)

    def get(self):
        om = get_omega(self.args)
        local = self.args['<path>']
        name = self.args['<name>']
        try:
            # try lazy get first to suppport large dataframes
            obj = om.datasets.get(name, lazy=True)
        except:
            obj = om.datasets.get(name)
        csvkwargs = self.parse_kwargs('--csv', index=False)
        is_csv = self.args.get('--format') == 'csv' or hasattr(obj, 'to_csv') or anyext(local, '.csv')
        is_binary = self.args.get('--format') == 'binary' or hasattr(obj, 'read')
        if is_csv and not is_binary:
            obj.to_csv(local, **csvkwargs)
        elif is_binary:
            with smart_open.open(local, 'wb') as fout:
                while True:
                    data = obj.read(1024 * 10)
                    if not data:
                        break
                    fout.write(data)
        self.logger.debug(local)


anyext = lambda n, exts: any(n.endswith(ext) for ext in exts.split(','))
