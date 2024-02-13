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

    def get(self, name, obj=None, collection=None, vector_size=None, raw=False, top=1, distance=None, **kwargs):
        if obj is not None:
            data = self.find_similar(name, obj, top=top, distance=distance)
            return data
        return DocumentIndex(name, embedding_model=None, store=self)

    def put(self, obj, name, collection=None, vector_size=None, attributes=None, append=True, **kwargs):
        if append is False:
            self.delete(name)
        meta = self.data_store.metadata(name)
        collection = collection or meta.kind_meta['collection'] or self._default_collection(name)
        if meta is None:
            url = obj
            meta = self._put_as_connection(url, name, collection=collection,
                                           attributes=attributes, **kwargs)
        elif meta is not None:
            self._put_via(name, obj, collection=collection, vector_size=vector_size)
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
            'sqlalchemy_connection': str(url),
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

    def _put_via(self, name, obj, collection=None, vector_size=None, **kwargs):
        meta = self.data_store.metadata(name)
        collection = collection or meta.kind_meta.get('collection') or self._default_collection(name)
        vector_size = vector_size or meta.kind_meta['collections'][collection]['vector_size']
        self.insert_chunk(obj, name, collection, vector_size, **kwargs)

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
    def __init__(self, name, embedding_model=None, store=None):
        self.name = name
        self.model: GenAIModel = embedding_model
        self.store: VectorStore = store

    def __repr__(self):
        return f'DocumentIndex({self.name})'

    def build(self, documents, loader=None):
        for document in documents:
            if callable(loader):
                document = loader(document)
            self._insert_document(document)

    def _insert_document(self, document):
        if isinstance(document, (list, tuple)):
            # (text, embedding [, attributes])
            text, embedding, *attributes = document
            self.insert_document(text, embedding, attributes)
        elif isinstance(document, dict) and 'text' in document:
            # dict(text=, embedding=, attribute=)
            self.insert_document(document['text'], document['embedding'],
                                 document.get('attributes'))
        elif isinstance(document, str):
            # pure text, let's embed first
            text = document
            embedding = self.model.embed(text)
            attributes = None
            self.insert_document(text, embedding, attributes)
        elif callable(document):
            document = document(document)
            self._insert_document(document)

    def clear(self, filter=None, **kwargs):
        self.store.drop(self.name, )

    def insert_document(self, text, embedding, attributes):
        self.store.insert_chunk(self.name, text, embedding, attributes)

    def retrieve(self, document, n=1, filter=None, **kwargs):
        self.store.find_similar(self.name, document, n=1, filter=filter, **kwargs)
