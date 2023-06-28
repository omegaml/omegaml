import smart_open
import warnings
from glob import iglob
from itertools import tee, islice
from markitdown import MarkItDown
from omegaml.backends.basedata import BaseDataBackend
from omegaml.backends.genai import GenAIModel
from omegaml.backends.genai.embedding import SimpleEmbeddingModel
from pathlib import Path
from types import GeneratorType, NoneType
from uuid import uuid4

"""
# create a document index
# -- the connection string is a URL to the postgres database
# -- the collection is the table name
# -- the embedding_model is the GenAIModel to use for embedding, it needs to support the embed() method
# -- this will create a Metadata object that stores the connection string, the collection name, and the embedding model
om.datasets.put('pgvector://postgres:test@localhost:5432/postgres', 'index/foobar', embedding_model='model/foobar')
# store documents
# - list of chunks : dict(text=, embedding=, attributes={})
# - list of tuple (text, embedding [, attributes]) # bare embedding format
om.datasets.put(documents, 'index/foobar')
# retrieve similar documents
om.datasets.get('index/foobar', like='text')
# retrieve the index
index = om.dataset.get('index/foobar', raw=True)
index.build(documents)
index.insert_
"""


class VectorStore:
    def load(self, name, store=None, vector_size=None, embedding_model=None, index_cls=None, **kwargs):
        index_cls = index_cls or DocumentIndex
        embedding_model = embedding_model if embedding_model is not None else SimpleEmbeddingModel()
        self.index = index_cls(name,
                               store=store,
                               vector_size=vector_size,
                               embedding_model=embedding_model, **kwargs)
        return self

    def insert_chunks(self, chunks, name, embeddings, attributes, **kwargs):
        raise NotImplementedError

    def find_similar(self, name, obj, n=1, filter=None, **kwargs):
        raise NotImplementedError

    def delete(self, name, obj=None, filter=None, **kwargs):
        raise NotImplementedError


class VectorStoreBackend(VectorStore, BaseDataBackend):
    KIND = 'vector.conx'
    PROMOTE = 'metadata'

    def get(self, name, query=None, document=None, collection=None, vector_size=None, embedding_model=None,
            raw=False, top=1, distance=None, **kwargs):
        meta = self.data_store.metadata(name)
        document = query or document
        if meta is None:
            return None
        if isinstance(embedding_model, (NoneType, str)):
            collection, vector_size, model = self._get_collection(name)
            real_embedding_model = self.model_store.get(embedding_model or model)
        else:
            real_embedding_model = embedding_model
        self.vector_store: VectorStore = self.load(name, store=self, vector_size=vector_size,
                                                   embedding_model=real_embedding_model)
        if document is not None:
            data = self.vector_store.index.retrieve(document, top=top, distance=distance)
            return data
        return self.vector_store.index

    def put(self, obj, name, collection=None, vector_size=None, embedding_model=None,
            attributes=None, append=True, loader=None, chunker=None, **kwargs):
        """ Create a vector store, or insert a document into an existing store

        Args:
            obj (str|list|tuple|dict): if an object by <name> does not exist yet, pass the
               connection string. If it does exist, pass the document to insert, a list of documents,
               a tuple of (chunks, embeddings, attributes), or a dict(chunks=, embeddings=, attributes=).
            name (str): name of the vector store
            collection (str): the name of the collection of documents inside the vector store
            vector_size:
            embedding_model:
            attributes:
            append:
            loader:
            chunker:
            **kwargs:

        Returns:

        """
        if append is False:
            self.delete(name)
        meta = self.data_store.metadata(name)
        if meta is None:
            url = obj
            collection = collection or self._default_collection(name)
            meta = self._put_as_connection(url, name, collection=collection,
                                           attributes=attributes, **kwargs)
            # update kind_meta to reflect all collections stored through this vectordb
            collections = meta.kind_meta.setdefault('collections', {})
            collections[collection] = {
                'vector_size': vector_size,
                'embedding_model': str(embedding_model),
            }
        elif meta is not None:
            if isinstance(embedding_model, (NoneType, str)):
                collection, vector_size, model = self._get_collection(name)
                real_embedding_model = self.model_store.get(embedding_model or model)
            else:
                real_embedding_model = embedding_model
                vector_size = vector_size or getattr(real_embedding_model, 'dimensions', None)
            self._put_via(name, obj, collection=collection,
                          vector_size=vector_size, embedding_model=real_embedding_model,
                          loader=loader, chunker=chunker)
        else:
            raise ValueError('type {} is not supported by {}'.format(type(obj), self.KIND))
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

    def _put_via(self, name, obj, collection=None, vector_size=None, embedding_model=None, loader=None, chunker=None,
                 **kwargs):
        meta = self.data_store.metadata(name)
        collection = collection or meta.kind_meta.get('collection') or self._default_collection(name)
        vector_size = vector_size or meta.kind_meta['collections'][collection]['vector_size']
        index: DocumentIndex = self.get(name, vector_size=vector_size, embedding_model=embedding_model)
        index.insert(obj, chunker=chunker)
        return index

    def _get_collection(self, name):
        meta = self.data_store.metadata(name)
        collection = meta.kind_meta['collection'] or self._default_collection(name)
        vector_size = meta.kind_meta['collections'][collection].get('vector_size')
        model = meta.kind_meta['collections'][collection].get('embedding_model')
        return collection, vector_size, model

    def _default_collection(self, name):
        if name is None:
            return name
        if not name.startswith(':'):
            name = f'{self.data_store.bucket}_{name}'
        else:
            name = name[1:]
        return name


class DocumentIndex:
    """ Abstract implementation for a document index

    The DocumentIndex is a high-level abstraction for an embedding-based document index.
    It takes an embedding model and a vector store as it's base

    """

    def __init__(self, name, store=None, vector_size=None, embedding_model=None, **kwargs):
        self.name = name
        self.store: VectorStore = store
        self.model: GenAIModel = embedding_model
        self.vector_size = vector_size

    def __repr__(self):
        return f'DocumentIndex({self.name})'

    def build(self, documents, append=False, loader=None, chunker=None):
        assert self._type_of_obj(documents) == 'documents', f"{type(documents)} is not iterable as documents"
        if not append:
            self.clear()
        for document in documents:
            if callable(loader):
                document = loader(document)
            self.insert(document, chunker=chunker)

    def load_from(self, path, chunker=None, loader=None):
        loader = loader or DocumentLoader()
        for document in loader.load(path):
            self.insert(document, chunker=chunker)

    def insert(self, document, chunker=None):
        self._insert_document(document, chunker=chunker)

    def retrieve(self, document, top=1, filter=None, distance=None, **kwargs):
        if isinstance(document, str):
            assert self.model is not None, "require embedding model to query by text"
            document = self.model.embed(document)[0]
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
            'pathlike': lambda obj: isinstance(obj, str) and (
                    Path(obj[:200]).exists() or obj.startswith('http')),
            # str
            'text': lambda obj: isinstance(obj, str),
            # text, attributes
            'text_tuple': lambda obj: isinstance(obj, (tuple, list)) and len(obj) > 1 and isinstance(probe[1], dict),
            # chunks, embeddings[, attributes]
            'embedded_tuple': lambda obj: isinstance(obj, (list, tuple)) and len(obj) > 1 and isinstance(probe[1],
                                                                                                         list),
            # dict(chunks=, embeddings=, attributes=None)
            'embedded_dict': lambda obj: isinstance(obj, dict) and 'chunks' in obj and 'embeddings' in obj,
            # list, tuple, generator of str|list|tuple|dict
            'documents': lambda obj: isinstance(obj, (list, tuple, GeneratorType)) and isinstance(probe[0],
                                                                                                  (str, list, tuple)),
        }
        for k, testfn in TYPES.items():
            if testfn(obj):
                return k
        raise ValueError(f'Cannot process obj of type {type(obj)}, it must be one of {TYPES.keys()}')

    def _insert_document(self, document, chunker=None, loader=None):
        _default_chunker = lambda document: [document]
        chunker = chunker or _default_chunker
        doc_type = self._type_of_obj(document)
        if doc_type == 'embedded_tuple':
            # (chunks, embeddings [, attributes]) # multiple document chunks for each tuple
            # (chunk, embedding, [, attributes]) # single document for each tuple
            chunks, embeddings, *attributes = document
            if isinstance(chunks, str):
                chunks = [chunks]
                embeddings = [embeddings]
            self._index_chunks(chunks, embeddings, attributes)
        elif doc_type == 'embedded_dict':
            # dict(chunks=, embeddings=, attribute=)
            self._index_chunks(document['chunks'], document['embeddings'],
                               document.get('attributes'))
        elif doc_type == 'text_tuple':
            # (text, attributes)
            assert self.model is not None, "need an embedding model to insert raw text"
            text, attributes = document
            embeddings = self.model.embed(chunker(text))
            self._index_chunks(chunker(text), embeddings, attributes)
        elif doc_type == 'text':
            # pure text, let's embed first
            assert self.model is not None, "need an embedding model to insert raw text"
            text = document
            embeddings = self.model.embed(chunker(text))
            attributes = None
            self._index_chunks(chunker(text), embeddings, attributes)
        elif doc_type == 'loader':
            document = document(document)
            self._insert_document(document, chunker=chunker)
        elif doc_type == 'documents':
            self.build(document, append=True, chunker=chunker)
        elif doc_type == 'pathlike':
            self.load_from(document, chunker=chunker, loader=loader)

    def _index_chunks(self, chunks, embeddings, attributes):
        self.store.insert_chunks(chunks, self.name, embeddings, attributes)


class DocumentLoader:
    def __init__(self, path=None):
        self.path = path
        self.md = MarkItDown()

    def load(self, path):
        if Path(path).exists:
            documents = self._from_path(path)
        elif path.startswith('http'):
            documents = self._from_url(path)
        else:
            raise ValueError(f'Cannot load documents from {path}')
        return documents

    def __iter__(self):
        return self._from_path(self.path)

    def _from_path(self, path):
        for fn in iglob(path):
            result = self.md.convert(fn)
            document = result.text_content
            yield document, dict(source=fn)

    def _from_url(self, url):
        with smart_open.open(url, 'rb') as fin:
            uuid = uuid4()
            fn = url.split('/')[-1]
            with open(f'/tmp/{uuid}/{fn}', 'rb') as fout:
                fout.write(fin.read())
            result = self.md.convert(fn)
            document = result.text_content
            Path(fn).unlink(missing_ok=True)
            yield document, dict(source=fn)
