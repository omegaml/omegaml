from unittest import TestCase, mock, skipUnless

import os
from contextlib import contextmanager
from omegaml.backends.genai.embedding import SimpleEmbeddingModel
from omegaml.backends.genai.index import DocumentIndex
from omegaml.backends.genai.pgvector import PGVectorBackend
from omegaml.tests.util import OmegaTestMixin
from unittest.mock import MagicMock


class GenAIModelTests(OmegaTestMixin, TestCase):
    def setUp(self):
        from omegaml import Omega
        self.om = Omega()
        self.om.models.register_backend(PGVectorBackend.KIND, PGVectorBackend)
        self.clean()
        self._mocked_store = []

    @mock.patch.object(PGVectorBackend, '_get_connection')
    def test_put_get_mocked(self, _get_connection):
        _get_connection.side_effect = self._mocked_get_connection
        self._test_put_get()

    @skipUnless(os.environ.get('TEST_PGVECTOR'), "skipping real pgvector test, set TEST_PGVECTOR=1 to run")
    def test_put_get_pgvector(self):
        # mocked pgvector backend
        # -- tests VectorStore protocol and PGVector implementation
        # -- does not test actual vector search
        self._test_put_get()

    def _test_put_get(self):
        # actual test code
        # -- requires postgres + pgvector to beg running at localhost:5432
        # -- docker run -e POSTGRES_PASSWORD=test -p 5432:5432 pgvector/pgvector:pg16
        om = self.om
        cnx_str = 'pgvector://postgres:test@localhost:5432/postgres'
        meta = om.datasets.put(cnx_str, 'mydocs',
                               replace=True,
                               collection='test',
                               vector_size=3)
        self.assertEqual(meta.kind, PGVectorBackend.KIND)
        self.assertEqual(meta.kind_meta['connection'], cnx_str)
        documents = [
            # (chunk, embedding)
            ('my text', [1, 2, 3]),
            ('my other text', [99, 100, 200]),
        ]
        om.datasets.put(documents, 'mydocs')
        chunks = om.datasets.get('mydocs', document=[3, 0, 0])
        self.assertTrue(len(chunks) > 0)
        self.assertIn('text', chunks[0])
        if 'distance' in chunks[0]:
            # this is only checked if we're not mocking pgvector
            self.assertEqual(chunks[0]['text'], 'my text')
            chunks = om.datasets.get('mydocs', document=[99, 150, 150])
            self.assertEqual(chunks[0]['text'], 'my other text')
            index = om.datasets.get('mydocs')
            self.assertIsInstance(index, DocumentIndex)

    @skipUnless(os.environ.get('TEST_PGVECTOR'), "skipping real pgvector test, set TEST_PGVECTOR=1 to run")
    def test_simple_embedding(self):
        om = self.om
        cnx_str = 'pgvector://postgres:test@localhost:5432/postgres'
        embedding_model = SimpleEmbeddingModel()
        documents = [
            'The quick brown fox jumps over the lazy dog',
        ]
        embedding_model.fit(documents)
        om.models.put(embedding_model, 'embedding')
        meta = om.datasets.put(cnx_str, 'mydocs',
                               embedding_model='embedding',
                               collection='test3',
                               vector_size=8,
                               replace=True)
        # check index is stored as expected
        self.assertEqual(meta.kind_meta['collections']['test3']['embedding_model'], 'embedding')
        mydocs = om.datasets.get('mydocs', model_store=om.models)
        self.assertIsInstance(mydocs.model, SimpleEmbeddingModel)
        # check index works as expected, using embedding model
        om.datasets.put(documents, 'mydocs', model_store=om.models)
        docs = om.datasets.get('mydocs', document='quick brown', model_store=om.models)
        self.assertTrue(len(docs) > 0)
        self.assertTrue(docs[0]['text'] == documents[0])
        with self.assertRaises(AssertionError):
            # if model_store=om.models is not passed, embedding model cannot be loaded
            om.datasets.get('mydocs', document='quick brown')
        # TODO test droping and recreating a collection with different vector size

    def test_index(self):
        om = self.om

    def _mocked_get_connection(self, name, session=False):
        store = self._mocked_store
        fields = ['text', 'source', 'embedding']

        def _add(obj):
            store.append(obj) if obj.__class__.__name__ == 'Chunk' else None

        def _results(*args, **kwargs):
            results = MagicMock()
            as_dict = lambda this: {a: getattr(this, a) for a in dir(this) if a in fields}
            results.all.side_effect = lambda: [as_dict(obj) or obj for obj in store]
            results.mappings.side_effect = lambda: results
            return results

        @contextmanager
        def session_mock():
            Session = MagicMock()
            Session.add.side_effect = _add
            Session.execute.side_effect = _results
            yield Session

        connection = session_mock() if session else MagicMock()
        return connection

    def _mocked_create_collection(self, *args, **kwargs):
        Document = MagicMock()
        Chunk = MagicMock()
        return Document, Chunk
