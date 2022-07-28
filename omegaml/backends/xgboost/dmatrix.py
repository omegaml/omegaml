import os

from omegaml.backends.basedata import BaseDataBackend

import xgboost as xgb


class XGBoostDMatrix(BaseDataBackend):
    KIND = 'xgboost.dmatrix'

    @classmethod
    def supports(cls, obj, name, **kwargs):
        return isinstance(obj, xgb.DMatrix)

    def get(self, name, version=-1, force_python=False, lazy=False, **kwargs):
        meta = self.data_store.metadata(name)
        key = self.data_store.object_store_key(name, 'bin')
        fname = self._tmp_packagefn(self.data_store, key)
        # DMatrix does not support reading from a file-like
        with open(fname, 'wb') as fout:
            fout.write(meta.gridfile.read())
        dm = xgb.DMatrix(fname)
        os.remove(fname)
        return dm

    def put(self, obj: xgb.DMatrix, name, attributes=None, **kwargs):
        key = self.data_store.object_store_key(name, 'bin')
        fname = self._tmp_packagefn(self.data_store, key)
        obj.save_binary(fname)
        with open(fname, 'rb') as fin:
            gridfile = self._store_to_file(self.data_store, fin, key, replace=True)
        os.remove(fname)
        kind_meta = {}
        return self.data_store.make_metadata(name, self.KIND,
                                             attributes=attributes,
                                             kind_meta=kind_meta,
                                             gridfile=gridfile,
                                             **kwargs).save()
