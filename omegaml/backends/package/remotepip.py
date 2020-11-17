import re
from os.path import basename

import os
import six

from omegaml.backends.basedata import BaseDataBackend
from omegaml.backends.package.packager import install_and_import


class PythonPipSourcedPackageData(BaseDataBackend):
    """
    Backend to support locally sourced custom scripts deployment to runtimes cluster

    This supports any pip-installable remote source like git, hg, svn, bzr

    Usage:
        # pypi package
        om.scripts.put('pypi://<pkgname>', '<pkgname>')
        # github hosted
        om.scripts.put('git+https://github.com/account/repo/<pkgname>', '<pkgname>')

        Upon om.scripts.get() pip install will be called to retrieve, build and load
        the package.

        # equiv. to pip install. Note for pypi, the pypi:// part is trimmed before calling pip.
        module = om.scripts.get('<pkgname>')

        Note you can use any specification supported by pip, e.g. to specify a
        particular version:

        om.scripts.put('pypi://<pkgname==version>', ...)
        om.scripts.put('git+https://....@tag#egg=<pkgname>', ...)

    Notes:
        the package specification is stored as meta.kind_meta['pip_source']
    """
    KIND = 'pipsrc.package'

    @classmethod
    def supports(self, obj, name, **kwargs):
        # see https://pip.pypa.io/en/stable/reference/pip_install/#vcs-support
        # pypi is our own protocol to designate pypi hosted packages
        # all others are pip supported formats
        # the pattern supports <source>:// and <source>+<protocol>:// formats
        # for pypi, .get() will remove the pypi:// part
        pip_protocols = '|'.join(('git', 'hg', 'svn', 'bzr', 'pypi'))
        pattern = r'^{}(\+.+)?://.*'
        is_pip_protocol = lambda v: re.match(pattern.format(pip_protocols), v)
        return isinstance(obj, six.string_types) and is_pip_protocol(obj)

    def put(self, obj, name, attributes=None, **kwargs):
        """
        save a python package

        :param obj: full path to package file or directory, sytanx as
                    pkg://path/to/dist.tar.gz or pkg://path/to/setup.py
        :param name: name of package. must be the actual name of the package
                     as specified in setup.py
        :return: the Metadata object
        """
        kind_meta = {
            'pip_source': obj,
        }
        return self.data_store._make_metadata(
            name=name,
            prefix=self.data_store.prefix,
            bucket=self.data_store.bucket,
            kind=PythonPipSourcedPackageData.KIND,
            kind_meta=kind_meta,
            attributes=attributes).save()

    def get(self, name, keep=False, **kwargs):
        """
        Load package from store, install it locally and load.

        :param name: the name of the package
        :param keep: keep the packages load path in sys.path, defaults to False
        :param kwargs:
        :return: the loaded module
        """
        pkgname = basename(name)
        meta = self.data_store.metadata(name)
        dstdir = self.packages_path
        pip_source = meta.kind_meta['pip_source']
        # pip does not know about pypi
        pip_name = pip_source.replace('pypi://', '')
        mod = install_and_import(pip_name, pkgname, dstdir, keep=keep)
        return mod

    @property
    def packages_path(self):
        return os.path.join(self.data_store.tmppath, 'packages')
