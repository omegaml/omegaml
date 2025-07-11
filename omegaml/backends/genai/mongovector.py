from omegaml.backends.genai.index import VectorStoreBackend
from omegaml.util import mongo_compatible


class MongoDBVectorStore(VectorStoreBackend):
    """
    MongoDB vector store for storing documents and their embeddings.
    """
    KIND = 'vector.conx'
    PROMOTE = 'metadata'

    @classmethod
    def supports(cls, obj, name, insert=False, data_store=None, model_store=None, *args, **kwargs):
        return str(obj).startswith('vector://')  # Always supports since it's MongoDB

    def _documents(self, name):
        return self.data_store.collection(f'vecdb_{name}_docs')

    def _chunks(self, name):
        return self.data_store.collection(f'vecdb_{name}_chunks')

    def list(self, name):
        """
        List all documents inside a collection.
        """
        docs = self._documents(name).find({},
                                          {'_id': 1, 'source': 1, 'attributes': 1})
        return [{'id': str(doc['_id']),
                 'source': doc.get('source', ''),
                 'attributes': doc.get('attributes', {})}
                for doc in docs]

    def insert_chunks(self, chunks, name, embeddings, attributes=None, **kwargs):
        attributes = attributes or {}
        source = attributes.get('source', None)

        # Insert the document metadata
        doc_id = self._documents(name).insert_one({
            'source': source,
            'attributes': attributes,
        }).inserted_id

        # Insert the chunks and their embeddings
        for text, embedding in zip(chunks, embeddings):
            self._chunks(name).insert_one({
                'document_id': doc_id,
                'text': text,
                'embedding': mongo_compatible(embedding),
            })

    def find_similar(self, name, obj, top=5, filter=None, distance='l2', **kwargs):
        # Create a pipeline to calculate distances
        obj = mongo_compatible(obj)
        pipeline = [
            {
                '$lookup': {
                    'from': self._documents(name).name,
                    'localField': 'document_id',
                    'foreignField': '_id',
                    'as': 'document'
                }
            },
            {
                '$unwind': '$document'
            },
            {
                '$project': {
                    'document_id': 1,
                    'text': 1,
                    'embedding': 1,
                    'source': '$document.source',
                    'attributes': '$document.attributes',
                    'distance': {
                        '$sqrt': {
                            '$sum': {
                                '$map': {
                                    'input': {
                                        '$range': [0, len(obj)],
                                    },
                                    'as': 'i',
                                    'in': {
                                        '$pow': [
                                            {'$subtract': [
                                                {'$arrayElemAt': ['$embedding', '$$i']},
                                                {'$arrayElemAt': [{'$literal': obj}, '$$i']}
                                            ]},
                                            2
                                        ]
                                    }
                                }
                            }
                        }
                    },
                }
            },
            {
                '$sort': {'distance': 1}
            },
            {
                '$limit': top
            }
        ]
        # Execute the aggregation pipeline
        results = list(self._chunks(name).aggregate(pipeline))[0:top]
        return results

    def delete(self, name, obj=None, filter=None, **kwargs):
        # Clear all stored documents and chunks
        filter = filter or {}
        if isinstance(obj, dict) and 'id' in obj:
            filter.update({'id': obj.get('id')})
        elif isinstance(obj, str):
            filter.update({'source': obj})
        elif isinstance(obj, (int, float)):
            filter.update({'id': str(obj)})
        elif obj is not None:
            raise ValueError("Object must be a dict with 'id', or a string matching source")
        doc_ids = self._documents(name).find(filter, {'_id': 1})
        self._documents(name).delete_many(filter)
        self._chunks(name).delete_many({
            'document_id': {'$in': [doc['_id'] for doc in doc_ids]}
        })
