import os

import six
from mongoengine import GridFSProxy

from omegaml.backends.basedata import BaseDataBackend
from omegaml.backends.package.packager import build_sdist, install_and_import, load_from_path


class PythonPackageData(BaseDataBackend):
    """
    Backend to support custom scripts deployment to runtimes cluster
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
            distdir = os.path.join(pkgsrc, 'dist')
            sdist = build_sdist(pkgsrc, distdir)
            version = sdist.metadata.version
            pkgname = sdist.metadata.name
            pkgdist = os.path.join(distdir, '{pkgname}-{version}.tar.gz'.format(**locals()))
        with open(pkgdist, 'rb') as fzip:
            fileid = self.data_store.fs.put(
                fzip, filename=self.data_store._get_obj_store_key(name, 'pkg'))
            gridfile = GridFSProxy(grid_id=fileid,
                                   db_alias='omega',
                                   collection_name=self.data_store.bucket)
        return self.data_store._make_metadata(
            name=name,
            prefix=self.data_store.prefix,
            bucket=self.data_store.bucket,
            kind=PythonPackageData.KIND,
            attributes=attributes,
            gridfile=gridfile).save()

    def get(self, name, **kwargs):
        """
        Load package from store, install it locally and load.

        :param name: the name of the package
        :param kwargs:
        :return: the loaded module
        """
        packagefname = '{}.tar.gz'.format(os.path.join(self.data_store.tmppath, name))
        dstdir = self.packages_path
        if not os.path.exists(os.path.join(dstdir, name)):
            filename = self.data_store._get_obj_store_key(name, '.pkg')
            outf = self.data_store.fs.get_version(filename)
            with open(packagefname, 'wb') as pkgf:
                pkgf.write(outf.read())
            mod = install_and_import(packagefname, name, dstdir)
        else:
            mod = load_from_path(name, dstdir)
        return mod

    @property
    def packages_path(self):
        return os.path.join(self.data_store.tmppath, 'packages')