from collections import Counter

import re
from bson import ObjectId

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
        return bool(re.match(r'^vector(\+mongodb)?://', str(obj)))  # Supports vector:// or vector+mongodb://

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
        source = attributes.get('source', '')
        attributes.setdefault('source', source)
        attributes.setdefault('tags', [])

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

    def find_similar(self, name, obj, top=5, filter=None, distance='l2', max_distance=None, **kwargs):
        # Create a pipeline to calculate distances
        obj = mongo_compatible(obj)
        lookup = [
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
        ]
        if filter:
            match = [{
                '$match': {
                    '$or': [
                        {f'document.attributes.{key}':
                             {'$in': values if isinstance(filter, list) else [values]}
                         for key, values in filter.items()}
                    ]
                }
            }]
        else:
            match = []
        project = [{
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
        }]
        sort = [
            {
                '$sort': {'distance': 1}
            },
            {
                '$limit': top
            }
        ]
        subset = [
            {
                '$match': {
                    'distance': {'$lte': float(max_distance)}
                }
            }
        ] if max_distance is not None else []
        pipeline = lookup + match + project + sort + subset
        # Execute the aggregation pipeline
        results = list(self._chunks(name).aggregate(pipeline))[0:top]
        return results

    def delete(self, name, obj=None, filter=None, **kwargs):
        # Clear all stored documents and chunks
        filter = filter or {}
        if isinstance(obj, dict) and 'id' in obj:
            filter.update({'_id': ObjectId(obj.get('id'))})
        elif isinstance(obj, str):
            filter.update({'source': obj})
        elif isinstance(obj, (int, float)):
            filter.update({'_id': ObjectId(str(obj))})
        elif obj is not None:
            raise ValueError("Object must be a dict with 'id', or a string matching source")
        doc_ids = self._documents(name).find(filter, {'_id': 1})
        self._documents(name).delete_many(filter)
        self._chunks(name).delete_many({
            'document_id': {'$in': [doc['_id'] for doc in doc_ids]}
        })

    def attributes(self, name, key=None):
        """
        Get the attributes of the vector store.

        Args:
            key (str, optional): If provided, returns attributes for this key only.

        Returns:
            dict: A dictionary of attributes for the vector store, where each value a dictionary of value counts.
        """
        # write in a way that is compatible with MongoDB as an agggregation pipeline
        key_filter = key
        pipeline = [
            {
                "$project": {
                    "keyValuePairs": {"$objectToArray": "$attributes"}
                    # Convert attributes to an array of key-value pairs
                }
            },
            {
                "$unwind": "$keyValuePairs"  # Deconstruct the array to output a document for each key-value pair
            },
            {
                "$unwind": "$keyValuePairs.v"  # Deconstruct the array of values for the 'tags' key
            },
            {
                "$group": {
                    "_id": {
                        "key": "$keyValuePairs.k",  # Group by the key
                        "value": "$keyValuePairs.v"  # Group by the value
                    },
                    "count": {"$sum": 1}  # Count occurrences
                }
            },
            {
                "$project": {
                    "key": "$_id.key",  # Restructure the output
                    "value": "$_id.value",
                    "count": 1,
                    "_id": 0  # Exclude the default _id field
                }
            },
            {
                "$sort": {
                    "key": 1,  # Sort by key
                    "value": 1  # Sort by value
                }
            }
        ]
        data = self._documents(name).aggregate(pipeline)
        results = {}
        for item in data:
            key, value, count = item.get('key'), item.get('value'), item.get('count')
            if key_filter and key != key_filter:
                continue
            counter = results.setdefault(key, Counter())
            counter[value] += count
        results = {key: dict(counts) for key, counts in results.items()}
        return results
