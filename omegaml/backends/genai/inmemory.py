from collections import Counter

import numpy as np
import re

from omegaml.backends.genai.index import VectorStoreBackend

INMEMORY_VECTOR_STORE = {}


class InMemoryVectorStore(VectorStoreBackend):
    """
    In-memory vector store for storing documents and their embeddings.
    """
    KIND = 'vecmem'
    PROMOTE = 'metadata'

    def load(self, name, store=None, vector_size=None, embedding_model=None, index_cls=None, **kwargs):
        super().load(name, store=store, vector_size=vector_size, embedding_model=embedding_model,
                     index_cls=index_cls, **kwargs)
        store = INMEMORY_VECTOR_STORE.setdefault(name, {})
        self.documents = store.setdefault('documents', {})  # Maps document IDs to their metadata
        self.chunks = store.setdefault('chunks', {})  # Maps document IDs to lists of chunks
        self.embeddings = store.setdefault('embeddings', {})  # Maps document IDs to their embeddings
        return self

    @classmethod
    def supports(cls, obj, name, insert=False, data_store=None, model_store=None, *args, **kwargs):
        return bool(re.match(r'^(vecmem|vector\+memory)://', str(obj)))

    def list(self, name):
        return [{
            'id': doc_id,
            'source': doc['source'],
            'attributes': doc['attributes'],
        } for doc_id, doc in self.documents.items()]

    def insert_chunks(self, chunks, name, embeddings, attributes, **kwargs):
        doc_id = len(self.documents) + 1  # Simple ID generation
        attributes = attributes or {}
        source = attributes.get('source', '')
        attributes.setdefault('source', source)
        attributes.setdefault('tags', [])
        # Store the document
        self.documents[doc_id] = {
            'source': source,
            'attributes': attributes,
        }

        # Store the chunks and their embeddings
        self.chunks[doc_id] = []
        self.embeddings[doc_id] = []

        for text, embedding in zip(chunks, embeddings):
            self.chunks[doc_id].append(text)
            self.embeddings[doc_id].append(embedding)

    def find_similar(self, name, obj, top=5, filter=None, distance=None, max_distance=None, **kwargs):
        # Calculate distances and find the top similar documents
        distance = distance or 'l2'
        distances = []
        all_match = lambda filter: all(
            set(value).issubset(self.documents[doc_id]['attributes'][key]) for key, value in filter.items())
        any_match = lambda filter: any(
            str(value) == str(self.documents[doc_id]['attributes'][key]) for key, value in filter.items())
        for doc_id, embeddings in self.embeddings.items():
            if filter and not (all_match(filter) or any_match(filter)):
                continue
            for embedding in embeddings:
                dist = self._calculate_distance(obj, embedding, distance)
                distances.append((doc_id, dist))

        # Sort by distance and get the top results
        distances.sort(key=lambda x: x[1])
        top_results = distances[:top]

        # Prepare the results
        results = []
        for doc_id, dist in top_results:
            if (dist >= max_distance) if max_distance is not None else False:
                continue
            results.append({
                'id': doc_id,
                'source': self.documents[doc_id]['source'],
                'attributes': self.documents[doc_id]['attributes'],
                'text': ' '.join(self.chunks[doc_id]),
                'distance': dist
            })
        return results

    def delete(self, name, obj=None, filter=None, **kwargs):
        # Clear all stored documents and chunks
        self.load(name)
        if obj:
            doc_id = obj.get('id')
            del self.documents[doc_id]
            del self.chunks[doc_id]
            del self.embeddings[doc_id]
        else:
            self.documents.clear()
            self.chunks.clear()
            self.embeddings.clear()

    def attributes(self, name, key=None):
        results = {}
        for doc in self.documents.values():
            for k, values in doc.get('attributes', {}).items():
                if key and k != key:
                    continue
                counter = results.setdefault(k, Counter())
                counter.update(values if isinstance(values, list) else [values])
        results = {key: dict(counts) for key, counts in results.items()}
        return results

    def _calculate_distance(self, vec1, vec2, metric):
        if metric == 'l2':
            return np.linalg.norm(np.array(vec1) - np.array(vec2))
        elif metric == 'cos':
            return 1 - np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        else:
            raise ValueError(f"Unsupported distance metric: {metric}")
