import tempfile
from os.path import basename, dirname
from subprocess import run

import os
import six
from shutil import make_archive, unpack_archive

from omegaml.backends.basedata import BaseDataBackend


class MLFlowProjectBackend(BaseDataBackend):
    """
    Backend to support storage of MLFlow projects

    Usage:
        om.scripts.put('mlflow://path/to/MLProject', 'myproject')
        om.scripts.get('myproject')

    See Also:
        https://www.mlflow.org/docs/latest/projects.html#project-directories
    """
    KIND = 'mlflow.project'
    MLFLOW_PREFIX = 'mlflow://'

    @classmethod
    def supports(self, obj, name, **kwargs):
        is_mlflow_prefix = isinstance(obj, six.string_types) and obj.startswith(self.MLFLOW_PREFIX)
        is_mlflow_kind = kwargs.get('kind') == self.KIND
        return is_mlflow_kind or is_mlflow_prefix

    def put(self, obj, name, attributes=None, **kwargs):
        """
        save a MLFlow project

        :param obj: full path to the MLFlow project directory
                    mlflow://path/to/MLProject
        :param name: name to store
        :return: the Metadata object
        """
        pkgsrc = obj.split(self.MLFLOW_PREFIX)[-1]
        if os.path.exists(pkgsrc):
            distdir = os.path.join(pkgsrc, 'dist')
            os.makedirs(distdir, exist_ok=True)
            tarfn = os.path.join(distdir, f'{name}')
            pkgdist = make_archive(tarfn, 'gztar', root_dir=pkgsrc, base_dir='.')
        else:
            raise FileNotFoundError(pkgsrc)
        filename = self.data_store.object_store_key(name, 'pkg', hashed=True)
        gridfile = self._store_to_file(self.data_store, pkgdist, filename)
        return self.data_store._make_metadata(
            name=name,
            prefix=self.data_store.prefix,
            bucket=self.data_store.bucket,
            kind=self.KIND,
            attributes=attributes,
            gridfile=gridfile).save()

    def get(self, name, localpath=None, **kwargs):
        """
        Load MLFlow project from store

        This copies the projects's .tar.gz file from om.scripts to a local temp
        path and returns the MLFlowProject to it

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
        unpack_archive(packagefname, dstdir)
        if localpath:
            mod = localpath
        else:
            mod = MLFlowProject(dstdir)
        return mod

    @property
    def packages_path(self):
        return os.path.join(self.data_store.tmppath, 'packages')


class MLFlowProject:
    """ a proxy to the MLFlow project that runs a script

    This provides the mod.run() interface for scripts so that
    we can use the same semantics for mlflow projects and pypi
    packages
    """

    def __init__(self, uri):
        self.uri = uri

    def run(self, om, pure_python=False, conda=True, **kwargs):
        options = ' '.join(f'--{k.replace("_", "-")} {v}' for k, v in kwargs.items())
        if not conda:
            options += ' --no-conda'
        tmpdir = tempfile.mkdtemp()
        # fix issue
        with open(os.path.join(tmpdir, 'activate'), 'w') as fout:
            fout.write('#/bin/bash')
            fout.write('conda activate %1')
        cmd = fr'PATH={tmpdir}:$PATH; cd {tmpdir}; chmod +x ./activate; mlflow run {options} {self.uri}'
        print(cmd)
        output = run(cmd, capture_output=True, shell=True)
        print(output)
        if output.stderr:
            output = {
                'stdout': output.stdout.decode('utf8'),
                'stderr': output.stderr.decode('utf8'),
            }
        else:
            output = output.stdout.decode('utf8')
        return {
            'output': output,
        }
