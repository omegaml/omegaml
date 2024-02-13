from types import GeneratorType

import warnings

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


class VectorStore(BaseDataBackend):
    KIND = 'vector.conx'
    PROMOTE = 'metadata'

    def get(self, name, obj=None, collection=None, vector_size=None, embedding_model=None,
            raw=False, top=1, distance=None, **kwargs):
        index = DocumentIndex(name, store=self, vector_size=vector_size,
                              embedding_model=embedding_model)
        if obj is not None:
            data = index.retrieve(obj, top=top, distance=distance)
            return data
        return index

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

    def insert_chunk(self, obj, name, embedding, attributes, **kwargs):
        raise NotImplementedError

    def find_similar(self, name, obj, n=1, filter=None, **kwargs):
        raise NotImplementedError

    def delete(self, name, obj=None, filter=None, **kwargs):
        raise NotImplementedError

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

    def _put_via(self, name, obj, collection=None, vector_size=None, embedding_model=None, **kwargs):
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
    def __init__(self, name, store=None, vector_size=None, embedding_model=None):
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

    def insert(self, document):
        self._insert_document(document)

    def retrieve(self, document, top=1, filter=None, distance=None, **kwargs):
        return self.store.find_similar(self.name, document,
                                       top=top, filter=filter, distance=distance, **kwargs)

    def clear(self, filter=None, **kwargs):
        self.store.delete(self.name, filter=filter, **kwargs)

    def _type_of_obj(self, obj):
        TYPES = {
            'documents': lambda obj: isinstance(obj, (list, tuple, GeneratorType)) and isinstance(obj[0], (list, tuple, dict)),
            'embedded_tuple': lambda obj: isinstance(obj, (list, tuple)) and not isinstance(obj[0], (list, tuple, GeneratorType)),
            'embedded_dict': lambda obj: isinstance(obj, dict) and 'text' in obj,
            'text': lambda obj: isinstance(obj, str),
            'loader': lambda obj: callable(obj),
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
        elif doc_type == 'text':
            # pure text, let's embed first
            text = document
            assert self.model is not None, "need an embedding model to insert raw text"
            embedding = self.model.embed(text)
            attributes = None
            self._index_chunk(text, embedding, attributes)
        elif doc_type == 'loader':
            document = document(document)
            self._insert_document(document)
        elif doc_type == 'documents':
            self.build(document, append=True)

    def _index_chunk(self, text, embedding, attributes):
        self.store.insert_chunk(text, self.name, embedding, attributes)
