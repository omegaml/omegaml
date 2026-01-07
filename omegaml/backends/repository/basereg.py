import os
import shlex
import subprocess
from contextlib import contextmanager

from omegaml.util import tryOr


class ArtifactRepository:
    def __init__(self, url, repo=None, namespace=None):
        self._url = url
        self.repo = repo
        self.namespace = namespace

    def login(self, user, token):
        raise NotImplementedError

    def artifacts(self, filter=None, repo=None):
        raise NotImplementedError

    @property
    def members(self):
        raise NotImplementedError

    @property
    def url(self):
        return f'{self._url}' if not self.namespace else f'{self.url}/{self.namespace}'

    def artifact(self, digest, repo=None):
        raise NotImplementedError

    def add(self, path, repo=None):
        raise NotImplementedError

    def extract(self, path, digest=None, repo=None, **kwargs):
        raise NotImplementedError


class f:
    """ pipeline to call arbitrary function

    Usage:

        (expression) | f(json.loads)

    Syntax:

        (expression) | f(callable)

        equivalent of
            result = (expression)
            result = callable(result)
    """

    def __init__(self, fn=None, *args, **kwargs):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def _exec(self, data, *args, **kwargs):
        return self.fn(data, *args, **kwargs)

    def __ror__(self, data):
        return self._exec(data, *self.args, **self.kwargs)


@contextmanager
def chdir(path):
    """ temporarily change the working directory to `path`

    This uses `os.chdir` to change the directory and restores it
    after the `with` block finishes.

    Args:
        path (str): path to change the working directory to

    Usage:
        with chdir('/path/to/directory'):
           print('changed directory')

    Returns:
        None
    """
    prev = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(prev)


#: split a command line arguments according to shell semantics (preserving quoted strings as one)
s = lambda v: tryOr(lambda: shlex.split(v, posix=True), f'invalid {v}')
#: call subcommand, capturing output as c("command line with arguments")
c = lambda cmd: subprocess.run(s(cmd), check=True, capture_output=True).stdout
