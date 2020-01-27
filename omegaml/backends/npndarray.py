import numpy as np
from six import BytesIO

from omegaml.backends.basedata import BaseDataBackend


class NumpyNDArrayBackend(BaseDataBackend):
    """
    Store numpy NDArray of any shape or size

    The NDArray is serialized to a byte string and stored as a BLOB.
    Thus it can have arbitrary size and dimensions, ideal for image
    data and Tensors.
    """
    KIND = 'ndarray.bin'

    _save_method = 'np.save'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return isinstance(obj, np.ndarray)

    def put(self, obj, name, attributes=None, allow_pickle=False, **kwargs):
        # TODO associate meta.gridfile with actual fs file
        kind_meta = {
            'dtype': obj.dtype.name,
            'shape': obj.shape,
            'save_method': self._save_method,
            'allow_pickle': allow_pickle,
        }
        buf = BytesIO()
        np.save(buf, obj, allow_pickle=allow_pickle)
        buf.seek(0)
        fn = self.data_store.object_store_key(name, 'np', hashed=True)
        gridfile = self._store_to_file(self.data_store, buf, fn)
        return self.data_store.make_metadata(name, self.KIND, attributes=attributes,
                                             kind_meta=kind_meta,
                                             gridfile=gridfile,
                                             **kwargs).save()

    def get(self, name, version=-1, force_python=False, lazy=False, **kwargs):
        # TODO read file from meta.gridfile if exists, fallback to .fs only if not
        meta = self.data_store.metadata(name)
        fin = meta.gridfile
        if meta.kind_meta.get('save_method') == self._save_method:
            allow_pickle = meta.kind_meta.get('allow_pickle')
            loaded = self._load_from_npsave(fin, allow_pickle)
        else:
            dtype_name = meta.kind_meta['dtype']
            dtype = getattr(np, dtype_name, None)
            shape = meta.kind_meta['shape']
            loaded = self._load_from_stringbuffer(fin, dtype, shape)
        return loaded

    def _load_from_stringbuffer(self, fin, dtype, shape):
        return np.frombuffer(fin.read(), dtype=dtype).reshape(*shape)

    def _load_from_npsave(self, fin, allow_pickle):
        buf = BytesIO()
        buf.write(fin.read())
        fin.close()
        buf.seek(0)
        return np.load(buf, allow_pickle=allow_pickle)
