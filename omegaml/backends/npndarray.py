from omegaml.backends.basedata import BaseDataBackend
import numpy as np


class NumpyNDArrayBackend(BaseDataBackend):
    """
    Store numpy NDArray of any shape or size

    The NDArray is serialized to a byte string and stored as a BLOB.
    Thus it can have arbitrary size and dimensions, ideal for image
    data and Tensors.
    """
    KIND = 'ndarray.bin'

    @classmethod
    def supports(self, obj, name, **kwargs):
        return isinstance(obj, np.ndarray)

    def put(self, obj, name, attributes=None, **kwargs):
        kind_meta = {
            'dtype': obj.dtype.name,
            'shape': obj.shape,
        }
        fout = self.data_store.fs.new_file(filename=name)
        fout.write(obj.tostring())
        fout.close()
        return self.data_store.make_metadata(name, self.KIND, attributes=attributes,
                                             kind_meta=kind_meta,
                                             **kwargs).save()

    def get(self, name, version=-1, force_python=False, lazy=False, **kwargs):
        fin = self.data_store.fs.get_last_version(name)
        meta = self.data_store.metadata(name)
        dtype_name = meta.kind_meta['dtype']
        dtype = getattr(np, dtype_name, None)
        shape = meta.kind_meta['shape']
        return np.frombuffer(fin.read(), dtype=dtype).reshape(*shape)
