from pathlib import Path

from glob import glob, iglob

import warnings
from itertools import tee, islice
from types import GeneratorType

from omegaml.backends.basedata import BaseDataBackend
from omegaml.backends.genai import GenAIModel

"""
# raw documents
# documents is
# - list of chunks : dict(text=, embedding=, attributes={})
# - list of tuple (text, embedding [, attributes]) # bare embedding format
om.datasets.put(documents, 'index/foobar', model=embedding_model)
om.datasets.get('index/foobar', like='text')
index = om.dataset.get('index/foobar', raw=True)
index.build(documents)
index.insert_
"""


class VectorStore:
    def load(self, name, store=None, vector_size=None, embedding_model=None, index_cls=None, **kwargs):
        index_cls = index_cls or DocumentIndex
        self.index = index_cls(name,
                               store=store,
                               vector_size=vector_size,
                               embedding_model=embedding_model, **kwargs)
        return self

    def insert_chunk(self, obj, name, embedding, attributes, **kwargs):
        raise NotImplementedError

    def find_similar(self, name, obj, n=1, filter=None, **kwargs):
        raise NotImplementedError

    def delete(self, name, obj=None, filter=None, **kwargs):
        raise NotImplementedError


class VectorStoreBackend(VectorStore, BaseDataBackend):
    KIND = 'vector.conx'
    PROMOTE = 'metadata'

    def get(self, name, document=None, collection=None, vector_size=None, embedding_model=None,
            raw=False, top=1, distance=None, **kwargs):
        self.vector_store: VectorStore = self.load(name, store=self, vector_size=None, embedding_model=None)
        if document is not None:
            data = self.vector_store.index.retrieve(document, top=top, distance=distance)
            return data
        return self.vector_store.index

    def put(self, obj, name, collection=None, vector_size=None, embedding_model=None,
            attributes=None, append=True, **kwargs):
        if append is False:
            self.delete(name)
        meta = self.data_store.metadata(name)
        collection = collection or meta.kind_meta['collection'] or self._default_collection(name)
        if meta is None:
            url = obj
            meta = self._put_as_connection(url, name, collection=collection,
                                           attributes=attributes, **kwargs)
        elif meta is not None:
            self._put_via(name, obj, collection=collection, vector_size=vector_size, embedding_model=embedding_model)
        else:
            raise ValueError('type {} is not supported by {}'.format(type(obj), self.KIND))
        # update kind_meta to reflect all collections stored through this vectordb
        collections = meta.kind_meta.setdefault('collections', {})
        collections[collection] = {
            'vector_size': vector_size,
        }
        meta.attributes.update(attributes) if attributes else None
        return meta.save()

    def drop(self, name, obj=None, filter=None, force=True, **kwargs):
        try:
            self.delete(name, obj=obj, filter=filter, **kwargs)
        except Exception as e:
            text = f'Could not delete vector store for {name} due to {e}'
            if not force:
                raise ValueError(text)
            warnings.warn(text)
        return super().drop(name, force=force, **kwargs)

    def _put_as_connection(self, url, name, attributes=None,
                           collection=None, **kwargs):
        kind_meta = {
            'connection': str(url),
            'collection': collection,
            'kwargs': kwargs,
        }
        meta = self.data_store.metadata(name)
        if meta is not None:
            meta.kind_meta.update(kind_meta)
        else:
            meta = self.data_store.make_metadata(name, self.KIND,
                                                 kind_meta=kind_meta,
                                                 attributes=attributes)
        return meta.save()

    def _put_via(self, name, obj, collection=None, vector_size=None, embedding_model=None, loader=None, **kwargs):
        meta = self.data_store.metadata(name)
        collection = collection or meta.kind_meta.get('collection') or self._default_collection(name)
        vector_size = vector_size or meta.kind_meta['collections'][collection]['vector_size']
        index: DocumentIndex = self.get(name, vector_size=vector_size, embedding_model=embedding_model)
        index.insert(obj)
        return index

    def _get_collection(self, name):
        meta = self.data_store.metadata(name)
        collection = meta.kind_meta['collection'] or self._default_collection(name)
        vector_size = meta.kind_meta['collections'][collection].get('vector_size')
        return collection, vector_size

    def _default_collection(self, name):
        if name is None:
            return name
        if not name.startswith(':'):
            name = f'{self.data_store.bucket}_{name}'
        else:
            name = name[1:]
        return name


class DocumentIndex:
    def __init__(self, name, store=None, vector_size=None, embedding_model=None, **kwargs):
        self.name = name
        self.store: VectorStore = store
        self.model: GenAIModel = embedding_model
        self.vector_size = vector_size

    def __repr__(self):
        return f'DocumentIndex({self.name})'

    def build(self, documents, append=False, loader=None):
        assert self._type_of_obj(documents) == 'documents', f"{type(documents)} is not iterable as documents"
        if not append:
            self.clear()
        for document in documents:
            if callable(loader):
                document = loader(document)
            self.insert(document)

    def load_from(self, path):
        documents = DocumentLoader().load(path)
        self.insert(documents)

    def insert(self, document):
        self._insert_document(document)

    def retrieve(self, document, top=1, filter=None, distance=None, **kwargs):
        return self.store.find_similar(self.name, document,
                                       top=top, filter=filter, distance=distance, **kwargs)

    def clear(self, filter=None, **kwargs):
        self.store.delete(self.name, filter=filter, **kwargs)

    def _type_of_obj(self, obj):
        if isinstance(obj, GeneratorType):
            # enable probing of generator up to the first element
            obj, probe = tee(obj, 2)
            probe = list(islice(probe, 1))
        else:
            probe = obj
        TYPES = {
            # fn()
            'loader': lambda obj: callable(obj),
            # path-like
            'pathlike': lambda obj: isinstance(obj, str) and Path(obj).exists(),
            # str
            'text': lambda obj: isinstance(obj, str),
            # text, None[, attributes]
            'text_tupple': lambda obj: isinstance(obj, (tuple, list)) and len(obj) > 1 and probe[1] is None,
            # text, embedding[, attributes]
            'embedded_tuple': lambda obj: isinstance(obj, (list, tuple)) and len(obj) > 1 and isinstance(probe[0], str),
            # dict(text=, embedding=, attributes)
            'embedded_dict': lambda obj: isinstance(obj, dict) and 'text' in obj and 'embedding' in obj,
            # list, tuple, generator of str|list|tuple|dict
            'documents': lambda obj: isinstance(obj, (list, tuple, GeneratorType)) and isinstance(probe[0],
                                                                                                  (str, list, tuple)),
        }
        for k, testfn in TYPES.items():
            if testfn(obj):
                return k
        raise ValueError(f'Cannot process obj of type {type(obj)}, it must be one of {TYPES.keys()}')

    def _insert_document(self, document):
        doc_type = self._type_of_obj(document)
        if doc_type == 'embedded_tuple':
            # (text, embedding [, attributes])
            text, embedding, *attributes = document
            self._index_chunk(text, embedding, attributes)
        elif doc_type == 'embedded_dict':
            # dict(text=, embedding=, attribute=)
            self._index_chunk(document['text'], document['embedding'],
                              document.get('attributes'))
        elif doc_type == 'text_tuple':
            # pure text, let's embed first
            assert self.model is not None, "need an embedding model to insert raw text"
            text, attributes = document
            embedding = self.model.embed(text)
            self._index_chunk(text, embedding, attributes)
        elif doc_type == 'text':
            # pure text, let's embed first
            assert self.model is not None, "need an embedding model to insert raw text"
            text = document
            embedding = self.model.embed(text)
            attributes = None
            self._index_chunk(text, embedding, attributes)
        elif doc_type == 'loader':
            document = document(document)
            self._insert_document(document)
        elif doc_type == 'documents':
            self.build(document, append=True)
        elif doc_type == 'pathlike':
            self.load_from(document)

    def _index_chunk(self, text, embedding, attributes):
        self.store.insert_chunk(text, self.name, embedding, attributes)


class DocumentLoader:
    def load(self, path):
        documents = self._from_path(path)
        return documents

    def _from_path(self, path):
        for fn in iglob(path):
            with open(fn) as fin:
                document = fin.read()
                # needs splitting?
                yield document
