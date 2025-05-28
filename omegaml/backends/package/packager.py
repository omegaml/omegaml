import callable_pip as cpip
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def build_sdist(src, distdir):
    # uses the build package to create a source distribution
    # -- see https://build.pypa.io/en/stable/api.html#build.ProjectBuilder
    from build import ProjectBuilder
    setup_path = Path(src.replace('setup.py', ''))
    builder = ProjectBuilder(setup_path)
    builder.build('sdist', output_directory=distdir)
    sdist = sorted(Path(distdir).iterdir(), key=os.path.getmtime)[-1]
    return str(sdist)


def install_package(src, dst):
    cpip.main('install',
              src,
              '--force-reinstall',
              '--no-cache-dir',
              '--upgrade',
              '--target', dst)


def load_from_path(name, path, keep=False):
    import importlib
    sys.path.insert(0, path)
    try:
        if name in sys.modules:
            del sys.modules[name]
        if name in globals():
            del globals()[name]
        mod = importlib.import_module(name)
    finally:
        # remove the import path -- this is to avoid
        # however comes at the cust
        if not keep:
            sys.path.remove(path)
    return mod


def install_and_import(pkgfilename, package, installdir, keep=False):
    """

    Returns:
        object:
    """
    install_package(pkgfilename, installdir)
    mod = load_from_path(package, installdir, keep=keep)
    return mod


class RunnablePackageMixin:
    # mixin to Package backends to enable backend.perform('run') from tasks
    def run(self, name, *args, keep=False, om=None, **kwargs):
        mod = self.get(name, keep=keep)
        return mod.run(om, *args, **kwargs)


if __name__ == '__main__':
    basepath = os.path.join(os.path.dirname(__file__), '..')
    pkgpath = os.path.join(basepath, 'demo/helloworld')
    build_sdist(pkgpath)

    pkgfilename = os.path.join(basepath, 'demo/helloworld/dist/helloworld-1.0.tar.gz')
    installdir = '/tmp/xyz'
    install_and_import(pkgfilename, 'helloworld', installdir)

    import helloworld

    helloworld.hello()
