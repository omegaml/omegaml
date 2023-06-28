import json
import numpy as np

from omegaml.backends.genai.embedding import SimpleEmbeddingModel
from omegaml.backends.genai.index import VectorStoreBackend


class InMemoryVectorStore(VectorStoreBackend):
    """
    In-memory vector store for storing documents and their embeddings.
    """
    KIND = 'vecmem'
    PROMOTE = 'metadata'

    def load(self, name, store=None, vector_size=None, embedding_model=None, index_cls=None, **kwargs):
        embedding_model = embedding_model or SimpleEmbeddingModel()
        super().load(name, store=store, vector_size=vector_size, embedding_model=embedding_model, index_cls=index_cls,
                     **kwargs)
        self.documents = {}  # Maps document IDs to documents
        self.chunks = {}  # Maps document IDs to lists of chunks
        self.embeddings = {}  # Maps document IDs to their embeddings

    @classmethod
    def supports(cls, obj, name, insert=False, data_store=None, model_store=None, *args, **kwargs):
        return name.startswith('vecmem://')

    def insert_chunks(self, chunks, name, embeddings, attributes, **kwargs):
        doc_id = len(self.documents) + 1  # Simple ID generation
        source = attributes.get('source', None)
        attributes_json = json.dumps(attributes or {})

        # Store the document
        self.documents[doc_id] = {
            'source': source,
            'attributes': attributes_json
        }

        # Store the chunks and their embeddings
        self.chunks[doc_id] = []
        self.embeddings[doc_id] = []

        for text, embedding in zip(chunks, embeddings):
            self.chunks[doc_id].append(text)
            self.embeddings[doc_id].append(embedding)

    def find_similar(self, name, obj, top=5, filter=None, distance='l2', **kwargs):
        # Calculate distances and find the top similar documents
        distances = []
        for doc_id, embeddings in self.embeddings.items():
            for embedding in embeddings:
                dist = self._calculate_distance(obj, embedding, distance)
                distances.append((doc_id, dist))

        # Sort by distance and get the top results
        distances.sort(key=lambda x: x[1])
        top_results = distances[:top]

        # Prepare the results
        results = []
        for doc_id, dist in top_results:
            results.append({
                'id': doc_id,
                'source': self.documents[doc_id]['source'],
                'attributes': self.documents[doc_id]['attributes'],
                'chunks': self.chunks[doc_id],
                'distance': dist
            })
        return results

    def delete(self, name, obj=None, filter=None, **kwargs):
        # Clear all stored documents and chunks
        self.documents.clear()
        self.chunks.clear()
        self.embeddings.clear()

    def _calculate_distance(self, vec1, vec2, metric):
        if metric == 'l2':
            return np.linalg.norm(np.array(vec1) - np.array(vec2))
        elif metric == 'cos':
            return 1 - np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        else:
            raise ValueError(f"Unsupported distance metric: {metric}")
