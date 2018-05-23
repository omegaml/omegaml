import os
from mongoengine.fields import GridFSProxy
import six
from omegaml.backends.basedata import BaseDataBackend


class PythonPackageData(BaseDataBackend):
    KIND = 'python.package'

    @classmethod
    def supports(self, obj, name, **kwargs):
        if isinstance(obj, six.string_types):
            if os.path.exists(obj):
                return True
        return False

    def put(self, obj, name, **kwargs):
        key = self.data_store.object_store_key(name, '.package')
        with open(obj, 'rb')as fin:
            fileid = self.data_store.fs.put(fin, filename=key)
            gridfile = GridFSProxy(grid_id=fileid)
        meta = self.data_store.make_metadata(name, self.KIND, gridfile=gridfile)
        return meta.save()

    def get(self, name, **kwargs):
        raise NotImplementedError

    def install(self, name, path):
        raise NotImplementedError


def install_and_import(package):
    import importlib
    try:
        importlib.import_module(package)
    except ImportError:
        import pip
        pip.main(['install', package, '--target', '/tmp/xyz'])
    finally:
        mod = importlib.import_module(package)
        globals()[package] = mod
        return mod
