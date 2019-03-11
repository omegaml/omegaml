from __future__ import absolute_import

from nbconvert import SlidesExporter
from nbconvert.exporters.html import HTMLExporter
from nbconvert.exporters.pdf import PDFExporter
from traitlets.config import Config, six

from omegaml.notebook.jobs import OmegaJobs


class OmegaEnterpriseJobs(OmegaJobs):
    """
    Omega Jobs API
    """

    # TODO this class should be a proper backend class

    def export(self, name, localpath, format='html'):
        """
        Export a job or result file to HTML

        The job is exported in the given format. 

        :param name: the name of the job, as in jobs.get
        :param localpath: the path of the local file to write. If you
           specify an empty path or 'memory' a tuple of (body, resource) 
           is returned instead
        :param format: the output format. currently only :code:`'html'` is supported
        :return: the (data, resources) tuple as returned by nbconvert. For
           format html data is the HTML's body, for PDF it is the pdf file contents
        """
        # https://nbconvert.readthedocs.io/en/latest/nbconvert_library.html
        # (exporter class, filemode, config-values
        EXPORTERS = {
            'html': (HTMLExporter, '', {}),
            'htmlbody': (HTMLExporter, '', {}),
            'pdf': (PDFExporter, 'b', {}),
            'slides': (SlidesExporter, '', {'RevealHelpPreprocessor.url_prefix':
                                                'https://cdnjs.cloudflare.com/ajax/libs/reveal.js/3.6.0/'}),
        }
        # get exporter according to format
        if format not in EXPORTERS:
            raise ValueError('format {} is invalid. Choose one of {}'.format(format, EXPORTERS.keys()))
        exporter_cls, fmode, configkw = EXPORTERS[format]
        # prepare config
        # http://nbconvert.readthedocs.io/en/latest/nbconvert_library.html#Using-different-preprocessors
        c = Config()
        for k, v in six.iteritems(configkw):
            context, key = k.split('.')
            setattr(c[context], key, v)
        # get configured exporter
        exporter = exporter_cls(config=c)
        # get notebook, convert and store in file if requested
        notebook = self.get(name)
        (data, resources) = exporter.from_notebook_node(notebook)
        if localpath and localpath != 'memory':
            with open(localpath, 'w' + fmode) as fout:
                fout.write(data)
        return data, resources
