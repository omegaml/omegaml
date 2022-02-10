import base64
from os.path import basename, dirname

import json
import os
import re
import six
from shutil import make_archive, unpack_archive
from subprocess import run

from omegaml.backends.basedata import BaseDataBackend
from omegaml.runtimes.rsystem import rhelper
from omegaml.util import tryOr


class RPackageData(BaseDataBackend):
    """
    Backend to support locally sourced custom scripts deployment to runtimes cluster

    This supports any local setup.py

    Usage:
        om.scripts.put('R://path/to/app.R', 'myname')
        om.scripts.get('myname')

        Note that setup.py must minimally specify the following. The
        name and packages kwargs must specify the same name as given
        in put(..., name)

            # setup.py
            from setuptools import setup
            setup(name='myname', packages=['myname'])

    See Also:
        https://packaging.python.org/tutorials/packaging-projects/
    """
    KIND = 'package.r'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return isinstance(obj, six.string_types) and obj.startswith('R://')

    def put(self, obj, name, attributes=None, **kwargs):
        """
        save a R package

        This takes the full path to a setuptools setup.py, or a directory
        containing a setup.py file. It then executes `python setup.py sdist`
        and stores the resulting .tar.gz file in om.scripts

        :param obj: full path to package file or directory, syntax as
                    pkg://path/to/dist.tar.gz or pkg://path/to/setup.py
        :param name: name of package. must be the actual name of the package
                     as specified in setup.py
        :return: the Metadata object
        """
        pkgsrc = pkgdist = obj.split('//')[1]
        pkgsrc = pkgsrc.replace('app.R', '')
        if not 'tar.gz' in os.path.basename(pkgdist):
            distdir = os.path.join(pkgsrc, 'dist')
            os.makedirs(distdir, exist_ok=True)
            base_name = os.path.join(distdir, f'{name}')
            pkgdist = make_archive(base_name, 'gztar', pkgsrc)
        filename = self.data_store.object_store_key(name, 'pkg', hashed=True)
        gridfile = self._store_to_file(self.data_store, pkgdist, filename)
        return self.data_store._make_metadata(
            name=name,
            prefix=self.data_store.prefix,
            bucket=self.data_store.bucket,
            kind=RPackageData.KIND,
            attributes=attributes,
            gridfile=gridfile).save()

    def get(self, name, localpath=None, keep=False, install=True, **kwargs):
        """
        Load package from store, install it locally and load.

        This copies the package's .tar.gz file from om.scripts to a local temp
        path and runs `pip install` on it.

        :param name: the name of the package
        :param keep: keep the packages load path in sys.path, defaults to False
        :param localpath: the local path to store the package
        :param install: if True call pip install on the retrieved package
        :param kwargs:
        :return: the loaded module
        """
        pkgname = basename(name)
        dstdir = localpath or self.data_store.tmppath
        packagefname = '{}.tar.gz'.format(os.path.join(localpath or self.packages_path, pkgname))
        os.makedirs(dirname(packagefname), exist_ok=True)
        meta = self.data_store.metadata(name)
        outf = meta.gridfile
        with open(packagefname, 'wb') as pkgf:
            pkgf.write(outf.read())
        if install:
            unpack_archive(packagefname, dstdir)
            mod = RScript(dstdir)
        else:
            mod = os.path.join(dstdir, pkgname)
        return mod

    @property
    def packages_path(self):
        return os.path.join(self.data_store.tmppath, 'packages')


class RScript:
    """ a Python proxy to the R process that runs a script

    This provides the mod.run() interface for scripts so that
    we can use the same semantics for R and python scripts.
    """
    def __init__(self, appdir):
        self.appdir = appdir

    def run(self, om, **kwargs):
        """ run the script in R session

        Usage:
            The script must exist as {self.appdir}/app.R. It must implement
            the omega_run()

            Example script:
            # app.R
            library(jsonlite)
            omega_run <- function(x, kwargs) {
               s <- fromJSON(rawToChar(base64_dec(kwargs)))
               s$message <- "hello from R"
               return(toJSON(s))
            }

        How it works:
            - If an R session is active, will run the script by calling the script's omega_run function
            - If no R session is active, will use RScript to source the script and run omega_run function
            - Expects the output to be in JSON format

        """
        r = rhelper()
        if r is None:
            r_kwargs = base64.b64encode(json.dumps(kwargs).encode('utf8')).decode('ascii')
            rcmd = fr'Rscript -e source("{self.appdir}/app.R") -e omega_run(0,"{r_kwargs}")'
            output = run(rcmd.split(' '), capture_output=True)
            output = output.stdout
        else:
            r.source(f'./{self.appdir}/app.R')
            output = r.omega_run(om, kwargs)
        return tryOr(lambda: json.loads(output), output)
