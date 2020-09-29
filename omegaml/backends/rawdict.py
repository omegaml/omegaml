from pymongo.collection import Collection

from omegaml.backends.basedata import BaseDataBackend
from omegaml.mdataframe import MDataFrame
from omegaml.util import json_normalize, PickableCollection


class PandasRawDictBackend(BaseDataBackend):
    """
    OmegaStore backend to support arbitrary collections

    Usage:
        # store any collection as part of metadata
        coll = db['some_collection']
        om.datasets.put(coll, 'foo')
        => Metadata(name='foo', collection='some_collection', ...)
        # parse the collection using pandas.io.json_normalize
        df = om.datasets.get('foo')
        # use an alternate parser that accepts dict|list(dict)
        df = om.datasets.get('foo', parser=some_fn)
        # get a MDataFrame
        om.datasets.getl('foo')
        # preserve all document keys, including _id
        om.datasets.getl('foo', raw=True)
    """
    KIND = 'pandas.rawdict'

    @classmethod
    def supports(self, obj, name, as_raw=None, **kwargs):
        return (as_raw and isinstance(obj, dict)) or isinstance(obj, (Collection, PickableCollection))

    def get(self, name, version=-1, lazy=False, raw=False, parser=None, filter=None, **kwargs):
        collection = self.data_store.collection(name)
        # json_normalize needs a list of dicts to work, not a generator
        json_normalizer = lambda v: json_normalize([r for r in v])
        parser = parser or json_normalizer
        query = filter or kwargs
        mdf = MDataFrame(collection, query=query, parser=parser, raw=raw, **kwargs)
        return mdf if lazy else mdf.value

    def put(self, obj, name, attributes=None, **kwargs):
        if isinstance(obj, dict):
            # actual data, just insert
            collection = self.data_store.collection(name)
            collection.insert(obj)
        else:
            # already a collection, import it to metadata
            collection = obj
        meta = self.data_store._make_metadata(name,
                                              kind=self.KIND,
                                              collection=collection.name,
                                              attributes=attributes,
                                              **kwargs)
        return meta.save()
