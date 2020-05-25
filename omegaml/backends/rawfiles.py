import os
import six

from omegaml.backends.basedata import BaseDataBackend


class PythonRawFileBackend(BaseDataBackend):
    """
    OmegaStore backend to support arbitrary files
    """
    KIND = 'python.file'

    @classmethod
    def supports(self, obj, name, as_raw=None, **kwargs):
        is_filelike = hasattr(obj, 'read')
        return is_filelike or self._is_path(self, obj)

    def get(self, name, version=-1, lazy=False, **kwargs):
        return self.data_store.metadata(name, **kwargs).gridfile

    def put(self, obj, name, attributes=None, encoding=None, **kwargs):
        self.data_store.drop(name, force=True)
        storekey = self.data_store.object_store_key(name, 'file', hashed=True)
        gridfile = self._store_to_file(self.data_store, obj, storekey, encoding=encoding)
        return self.data_store._make_metadata(
            name=name,
            prefix=self.data_store.prefix,
            bucket=self.data_store.bucket,
            kind=self.KIND,
            attributes=attributes,
            gridfile=gridfile).save()
