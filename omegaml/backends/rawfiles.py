import os
import six
from mongoengine import GridFSProxy

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

    def _is_path(self, obj):
        return isinstance(obj, six.string_types) and os.path.exists(obj)

    def get(self, name, version=-1, lazy=False, **kwargs):
        return self.data_store.metadata(name, **kwargs).gridfile

    def put(self, obj, name, attributes=None, encoding=None, **kwargs):
        self.data_store.drop(name, force=True)
        fn = self.data_store._get_obj_store_key(name, 'file')
        if self._is_path(obj):
            with open(obj, 'rb') as fin:
                fileid = self.data_store.fs.put(fin, filename=fn)
        else:
            fileid = self.data_store.fs.put(obj, filename=fn, encoding=encoding)
        gridfile = GridFSProxy(grid_id=fileid,
                               db_alias='omega',
                               collection_name=self.data_store.bucket)
        return self.data_store._make_metadata(
            name=name,
            prefix=self.data_store.prefix,
            bucket=self.data_store.bucket,
            kind=self.KIND,
            attributes=attributes,
            gridfile=gridfile).save()
