from __future__ import absolute_import

import threading

from hashlib import sha256

import logging

import warnings

from omegaml.store import qops
from omegaml.store.query import Filter
from omegaml.util import PickableCollection, ensure_base_collection, signature

logger = logging.getLogger(__name__)

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

    def __init__(self, collection, query=None, projection=None,
                 trusted=False, **kwargs):
        if isinstance(collection, FilteredCollection):
            # avoid cascading of FilteredCollections
            query = query or collection._fixed_query
            projection = projection or collection.projection
            collection = ensure_base_collection(collection)
        else:
            query = query or {}
        self._fixed_query = query
        self._trusted = trusted
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
        return Filter(self.collection, _trusted=self._trusted, **self._fixed_query).query

    def aggregate(self, pipeline, filter=None, **kwargs):
        query = dict(self.query)
        query.update(self._sanitize_filter(filter or {}))
        pipeline.insert(0, qops.MATCH(query))
        kwargs.update(allowDiskUse=True)
        return self.collection.aggregate(pipeline, **kwargs)

    def find(self, filter=None, trusted=False, **kwargs):
        query = dict(self.query)
        query.update(self._sanitize_filter(filter or {}, trusted=trusted))
        return self.collection.find(filter=query, **kwargs)

    def find_one(self, filter=None, *args, **kwargs):
        query = dict(self.query)
        query.update(self._sanitize_filter(filter or {}))
        return self.collection.find_one(query, *args, **kwargs)

    def find_one_and_delete(self, filter=None, **kwargs):
        query = dict(self.query)
        query.update(self._sanitize_filter(filter or {}))
        return self.collection.find_one_and_delete(query,
                                                   **kwargs)

    def find_one_and_replace(self, replacement, filter=None, **kwargs):
        query = dict(self.query)
        query.update(self._sanitize_filter(filter or {}))
        return self.collection.find_one_and_replace(query,
                                                    replacement,
                                                    **kwargs)

    def find_one_and_update(self, update, filter=None, **kwargs):
        query = dict(self.query)
        query.update(self._sanitize_filter(filter or {}))
        return self.collection.find_one_and_update(query,
                                                   update,
                                                   **kwargs)

    def estimated_document_count(self, **kwargs):
        return self.collection.estimated_document_count(**kwargs)

    def count_documents(self, filter=None, trusted=False, **kwargs):
        query = dict(self.query)
        query.update(self._sanitize_filter(filter or {}, trusted=trusted))
        return self.collection.count_documents(query, **kwargs)

    def distinct(self, key, filter=None, **kwargs):
        query = dict(self.query)
        query.update(self._sanitize_filter(filter or {}))
        return self.collection.distinct(key, filter=query, **kwargs)

    def create_index(self, keys, **kwargs):
        return self.collection.create_index(keys, **kwargs)

    def list_indexes(self, **kwargs):
        return self.collection.list_indexes(**kwargs)

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

    def _sanitize_filter(self, filter, trusted=False):
        from omegaml.store.queryops import sanitize_filter
        trusted = trusted or self._trusted
        should_sanitize = not trusted or trusted != signature(filter)
        sanitize_filter(filter) if should_sanitize else filter
        logger.debug(f'executing mongodb query filter {filter}')
        return filter

