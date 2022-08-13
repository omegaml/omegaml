import re

from omegaml.backends.basedata import BaseDataBackend
from omegaml.backends.mlflow.localprojects import MLFlowProject
from omegaml.backends.package.packager import RunnablePackageMixin


class MLFlowGitProjectBackend(RunnablePackageMixin, BaseDataBackend):
    """
    Backend to support git-sourced MLFlow projects

    This supports any git remote source that MLFlow supports

    Usage::

        om.scripts.put('mlflow+ssh://git@github.com/<user>/<repo>.git', '<pkgname>')
        om.scripts.put('mlflow+https://git@github.com/<user>/<repo>.git', '<pkgname>')
        om.scripts.put('https://github.com/<user>/<repo>', '<pkgname>', kind='mlflow.project')

    See Also:
        * https://packaging.python.org/tutorials/packaging-projects/
        * https://docs.github.com/en/get-started/getting-started-with-git/managing-remote-repositories#changing-a-remote-repositorys-url
    """
    KIND = 'mlflow.gitproject'
    MLFLOW_GIT_PREFIX = re.compile(r'^mlflow\+(git|ssh|https).*')
    GIT_PREFIX = 'https'

    @classmethod
    def supports(self, obj, name, **kwargs):
        is_mlflow_git = isinstance(obj, str) and self.MLFLOW_GIT_PREFIX.match(obj)
        is_git = isinstance(obj, str) and obj.startswith(self.GIT_PREFIX) and kwargs.get('kind') == self.KIND
        return is_mlflow_git or is_git

    def put(self, obj, name, attributes=None, **kwargs):
        """
        save a MLFlow git-sourceable project
        """
        git_uri = obj.replace('mlflow+', '')
        return self.data_store._make_metadata(
            name=name,
            prefix=self.data_store.prefix,
            bucket=self.data_store.bucket,
            kind=MLFlowGitProjectBackend.KIND,
            uri=git_uri,
            attributes=attributes).save()

    def get(self, name, **kwargs):
        """
        Load MLFlow project from git uri

        :return: the loaded module
        """
        meta = self.data_store.metadata(name)
        mod = MLFlowProject(meta.uri)
        return mod
