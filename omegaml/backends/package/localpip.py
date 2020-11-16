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
        om.scripts.put('pkg://path/to/setup.py')
    """
    KIND = 'python.package'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return isinstance(obj, six.string_types) and obj.startswith('pkg://')

    def put(self, obj, name, attributes=None, **kwargs):
        """
        save a python package

        :param obj: full path to package file or directory, sytanx as
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

    def get(self, name, keep=False, **kwargs):
        """
        Load package from store, install it locally and load.

        :param name: the name of the package
        :param keep: keep the packages load path in sys.path, defaults to False
        :param kwargs:
        :return: the loaded module
        """
        pkgname = basename(name)
        packagefname = '{}.tar.gz'.format(os.path.join(self.data_store.tmppath, pkgname))
        os.makedirs(dirname(packagefname), exist_ok=True)
        self.path = self.packages_path
        dstdir = self.path
        if not os.path.exists(os.path.join(dstdir, pkgname)):
            meta = self.data_store.metadata(name)
            outf = meta.gridfile
            with open(packagefname, 'wb') as pkgf:
                pkgf.write(outf.read())
            mod = install_and_import(packagefname, pkgname, dstdir, keep=keep)
        else:
            mod = load_from_path(pkgname, dstdir, keep=keep)
        return mod

    @property
    def packages_path(self):
        return os.path.join(self.data_store.tmppath, 'packages')
