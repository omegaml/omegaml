from __future__ import absolute_import

from omegaml.store import qops
from omegaml.store.query import Filter
from omegaml.util import PickableCollection, ensure_base_collection


class FilteredCollection:
    """
    A permanently filtered collection

    Supports all methods as a Collection does, however any filter or query
    argument is permanently set at instantiation

        fcoll = FilteredCollection(collection, query={ expression })

    Any subsequent operation will automatically apply the query expression.

    Note that v.v. a Collection and all methods that accept a filter as their first
    argument have a changed signature - the filter argument is optional
    with all FilteredCollection methods, as the filter is set at instantiation.

        Example:

            # in pymongo

            filter = {expression}
            coll.find_one_and_replace(filter, replace)

            # FilteredCollection

            coll = FilteredCollection(query={expression})
            coll.find_one_and_replace(replace, filter=None)

    This is so that calls to a FilteredCollection feel more natural, as opposed
    to specifying an empty filter argument on every call. Still, an additional
    filter can be specified on every method that accepts the filter= optional
    argument:

            # temporarily add another filter

            coll.find_one_and_replace(replace, filter={expression})

    Here expression will only apply to this particular method call. The
    global filter set by query= is unchanged.

    If no expression is given, the empty expression {} is assumed. To change
    the expression for the set fcoll.query = { expression }
    """

    def __init__(self, collection, query=None, projection=None, **kwargs):
        if isinstance(collection, FilteredCollection):
            # avoid cascading of FilteredCollections
            query = query or collection._fixed_query
            projection = projection or collection.projection
            collection = ensure_base_collection(collection)
        else:
            query = query or {}
        self._fixed_query = query
        self.projection = projection
        self.collection = PickableCollection(collection)

    @property
    def _Collection__database(self):
        return self.collection.database

    @property
    def name(self):
        return self.collection.name

    @property
    def database(self):
        return self.collection.database

    @property
    def query(self):
        return Filter(self.collection, **self._fixed_query).query

    def aggregate(self, pipeline, filter=None, **kwargs):
        query = dict(self.query)
        query.update(filter or {})
        pipeline.insert(0, qops.MATCH(query))
        kwargs.update(allowDiskUse=True)
        return self.collection.aggregate(pipeline, **kwargs)

    def find(self, filter=None, **kwargs):
        query = dict(self.query)
        query.update(filter or {})
        return self.collection.find(filter=query, **kwargs)

    def find_one(self, filter=None, *args, **kwargs):
        query = dict(self.query)
        query.update(filter or {})
        return self.collection.find_one(query, *args, **kwargs)

    def find_one_and_delete(self, filter=None, **kwargs):
        query = dict(self.query)
        query.update(filter or {})
        return self.collection.find_one_and_delete(query,
                                                   **kwargs)

    def find_one_and_replace(self, replacement, filter=None, **kwargs):
        query = dict(self.query)
        query.update(filter or {})
        return self.collection.find_one_and_replace(query,
                                                    replacement,
                                                    **kwargs)

    def find_one_and_update(self, update, filter=None, **kwargs):
        query = dict(self.query)
        query.update(filter or {})
        return self.collection.find_one_and_update(query,
                                                   update,
                                                   **kwargs)

    def count(self, filter=None, **kwargs):
        query = dict(self.query)
        query.update(filter or {})
        return self.collection.count(filter=query, **kwargs)

    def distinct(self, key, filter=None, **kwargs):
        query = dict(self.query)
        query.update(filter or {})
        return self.collection.distinct(key, filter=query, **kwargs)

    def create_index(self, keys, **kwargs):
        return self.collection.create_index(keys, **kwargs)

    def list_indexes(self, **kwargs):
        return self.collection.list_indexes(**kwargs)

    def group(self, key, initial, reduce, condition=None, **kwargs):
        condition = dict(self.query)
        condition.update(condition or {})
        return self.collection.group(key, condition, initial,
                                     reduce,
                                     **kwargs)

    def map_reduce(self, m, r, out, full_response=False, query=None, **kwargs):
        _query = dict(self.query)
        _query.update(query or {})
        return self.collection.map_reduce(m, r, out,
                                          full_response=False,
                                          query=_query, **kwargs)

    def inline_map_reduce(self, m, r, full_response=False,
                          query=None, **kwargs):
        _query = dict(self.query)
        _query.update(query or {})
        return self.collection.inline_map_reduce(m, r,
                                                 full_response=False, query=_query, **kwargs)

    def insert(self, *args, **kwargs):
        raise NotImplementedError(
            "deprecated in Collection and not implemented in FilteredCollection")

    def update(self, *args, **kwargs):
        raise NotImplementedError(
            "deprecated in Collection and not implemented in FilteredCollection")

    def remove(self, *args, **kwargs):
        raise NotImplementedError(
            "deprecated in Collection and not implemented in FilteredCollection")

    def find_and_modify(self, *args, **kwargs):
        raise NotImplementedError(
            "deprecated in Collection and not implemented in FilteredCollection")

    def ensure_index(self, *args, **kwargs):
        raise NotImplementedError(
            "deprecated in Collection and not implemented in FilteredCollection")

    def save(self, *args, **kwargs):
        raise NotImplementedError(
            "deprecated in Collection and not implemented in FilteredCollection")
