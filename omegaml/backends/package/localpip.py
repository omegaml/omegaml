from os.path import basename, dirname

import os
import six

from omegaml.backends.basedata import BaseDataBackend
from omegaml.backends.package.packager import build_sdist, install_and_import, load_from_path


class PythonPackageData(BaseDataBackend):
    """
    Backend to support locally sourced custom scripts deployment to runtimes cluster

    This supports any local setup.py

    Usage:
        om.scripts.put('pkg://path/to/setup.py', 'myname')
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
    KIND = 'python.package'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return isinstance(obj, six.string_types) and obj.startswith('pkg://')

    def put(self, obj, name, attributes=None, **kwargs):
        """
        save a python package

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
        if not 'tar.gz' in os.path.basename(pkgdist):
            pkgsrc = pkgsrc.replace('setup.py', '')
            distdir = os.path.join(pkgsrc, 'dist')
            sdist = build_sdist(pkgsrc, distdir)
            version = sdist.metadata.version
            pkgname = sdist.metadata.name
            pkgdist = os.path.join(distdir, '{pkgname}-{version}.tar.gz'.format(**locals()))
        filename = self.data_store.object_store_key(name, 'pkg', hashed=True)
        gridfile = self._store_to_file(self.data_store, pkgdist, filename)
        return self.data_store._make_metadata(
            name=name,
            prefix=self.data_store.prefix,
            bucket=self.data_store.bucket,
            kind=PythonPackageData.KIND,
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
        packagefname = '{}.tar.gz'.format(os.path.join(localpath or self.data_store.tmppath, pkgname))
        os.makedirs(dirname(packagefname), exist_ok=True)
        self.path = self.packages_path
        dstdir = localpath or self.path
        if not os.path.exists(os.path.join(dstdir, pkgname)):
            meta = self.data_store.metadata(name)
            outf = meta.gridfile
            with open(packagefname, 'wb') as pkgf:
                pkgf.write(outf.read())
            if install:
                mod = install_and_import(packagefname, pkgname, dstdir, keep=keep)
            else:
                mod = packagefname
        elif install:
            mod = load_from_path(pkgname, dstdir, keep=keep)
        else:
            mod = os.path.join(dstdir, pkgname)
        return mod

    @property
    def packages_path(self):
        return os.path.join(self.data_store.tmppath, 'packages')
