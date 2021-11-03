from omegaml.backends.basedata import BaseDataBackend
from omegaml.backends.mlflow.localprojects import MLFlowProject


class MLFlowGitProjectBackend(BaseDataBackend):
    """
    Backend to support git-sourced MLFlow projects

    This supports any git remote source that MLFlow supports

    Usage:
        om.scripts.put('mlflow+git://<user>/<repo>', '<pkgname>')

    See Also
        https://packaging.python.org/tutorials/packaging-projects/
    """
    KIND = 'mlflow.gitproject'
    MLFLOW_GIT_PREFIX = 'mlflow+git'
    GIT_PREFIX = 'https'

    @classmethod
    def supports(self, obj, name, **kwargs):
        is_mlflow_git = isinstance(obj, str) and obj.startswith(self.MLFLOW_GIT_PREFIX)
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
