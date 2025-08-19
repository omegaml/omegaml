from unittest import TestCase, mock

from contextlib import contextmanager
from io import BytesIO
from sklearn.exceptions import NotFittedError
from unittest.mock import MagicMock

from omegaml.backends.genai.dbmigrate import DatabaseMigrator
from omegaml.backends.genai.embedding import SimpleEmbeddingModel
from omegaml.backends.genai.index import DocumentIndex
from omegaml.backends.genai.pgvector import PGVectorBackend
from omegaml.client.util import subdict
from omegaml.tasks import omega_indexdocuments
from omegaml.tests.util import OmegaTestMixin


class PGVectorDBTests(OmegaTestMixin, TestCase):
    def setUp(self):
        from omegaml import Omega
        self.om = Omega()
        self.initparams()
        self.om.models.register_backend(self._vectordb_cls.KIND, self._vectordb_cls)
        self.clean()
        # uncomment to get debug logging for the PGVector backend
        # logging.getLogger('omegaml.backends.genai.pgvector').setLevel(logging.DEBUG)
        # logging.info('Running PGVectorDBTests with mocked backend')

    def initparams(self):
        self._vectordb_cls = PGVectorBackend
        self._mocked_store = []
        self._cnx_str = 'pgvector://postgres:test@localhost:5432/postgres'

    def test_put_get_mocked(self):
        with (mock.patch.object(self._vectordb_cls, '_get_connection', side_effect=self._mocked_get_connection),
              mock.patch.object(DatabaseMigrator, 'run_migrations', side_effect=lambda *args, **kwargs: None)):
            self._test_put_get()

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
        meta = om.datasets.put(self._cnx_str, 'mydocs',
                               replace=True,
                               collection='test',
                               vector_size=3)
        self.assertEqual(meta.kind, self._vectordb_cls.KIND)
        self.assertEqual(meta.kind_meta['connection'], self._cnx_str)
        documents = [
            # (chunk, embedding)
            ('my text', [1, 2, 3]),
            ('my other text', [99, 100, 200]),
        ]
        om.datasets.put(documents, 'mydocs')
        index = om.datasets.get('mydocs')
        self.assertIsInstance(index, DocumentIndex)
        self.assertEqual(len(index.list()), 2)
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

    def test_document_list(self):
        om = self.om
        meta = om.datasets.put(self._cnx_str, 'mydocs',
                               replace=True,
                               collection='test',
                               vector_size=3)
        documents = [
            ('my text', [1, 2, 3]),
            ('my other text', [99, 100, 200]),
        ]
        om.datasets.put(documents, 'mydocs')
        index = om.datasets.get('mydocs')
        documents = index.list()
        self.assertEqual([subdict(doc, ['source', 'attributes']) for doc in documents],
                         [{'source': '', 'attributes': {'tags': [], 'source': ''}},
                          {'source': '', 'attributes': {'tags': [], 'source': ''}}])

    def test_delete_index(self):
        om = self.om
        meta = om.datasets.put(self._cnx_str, 'mydocs',
                               replace=True,
                               collection='test',
                               vector_size=3)
        documents = [
            ('my text', [1, 2, 3]),
            ('my other text', [99, 100, 200]),
        ]
        om.datasets.put(documents, 'mydocs')
        index = om.datasets.get('mydocs')
        self.assertEqual(len(index.list()), 2)
        om.datasets.drop('mydocs')
        self.assertTrue('mydocs' not in om.datasets.list())

    def test_delete_document(self):
        om = self.om
        meta = om.datasets.put(self._cnx_str, 'mydocs',
                               replace=True,
                               collection='test',
                               vector_size=3)
        documents = [
            ('my text', [1, 2, 3]),
            ('my other text', [99, 100, 200]),
        ]
        om.datasets.put(documents, 'mydocs')
        index = om.datasets.get('mydocs')
        self.assertEqual(len(index.list()), 2)
        # delete a document
        index = om.datasets.get('mydocs')
        documents = index.list()
        om.datasets.drop('mydocs', obj=documents[0])
        self.assertEqual(len(index.list()), 1)
        om.datasets.drop('mydocs', obj=documents[0]['source'])
        self.assertEqual(len(index.list()), 0)

    def test_simple_embedding(self):
        om = self.om
        embedding_model = SimpleEmbeddingModel()
        documents = [
            'The quick brown fox jumps over the lazy dog',
        ]
        embedding_model.fit(documents)
        om.models.put(embedding_model, 'embedding')
        meta = om.datasets.put(self._cnx_str, 'mydocs',
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
        with self.assertRaises(NotFittedError):
            # if model_store=om.models is not passed, an unfitted model is used
            om.datasets.get('mydocs', document='quick brown')

    def test_attributes_filter(self):
        om = self.om
        embedding_model = SimpleEmbeddingModel()
        documents = [
            ('The quick brown fox jumps over the lazy dog', {'tags': ['animal']}),
            ('The lazy dog sleeps', {'tags': ['animal', 'lazy'], 'labels': ['lazy']}),
            ('A fast car zooms by', {'tags': ['vehicle']}),
        ]
        embedding_model.fit(list(doc for doc, attributes in documents))
        om.models.put(embedding_model, 'embedding')
        meta = om.datasets.put(self._cnx_str, 'mydocs',
                               embedding_model='embedding',
                               collection='test3',
                               vector_size=embedding_model.dimensions,
                               replace=True)
        # check index is stored as expected
        self.assertEqual(meta.kind_meta['collections']['test3']['embedding_model'], 'embedding')
        mydocs = om.datasets.get('mydocs', model_store=om.models)
        self.assertIsInstance(mydocs.model, SimpleEmbeddingModel)
        # check index works as expected, using embedding model
        om.datasets.put(documents, 'mydocs', model_store=om.models)
        # filter by attributes
        for doc, tag in documents:
            docs = om.datasets.get('mydocs', document=doc, model_store=om.models, tags=tag['tags'])
            self.assertTrue(len(docs) > 0)
            self.assertTrue(docs[0]['text'] == doc)
        # test there is never a document with the wrong tags
        docs = om.datasets.get('mydocs', document='quick brown',
                               model_store=om.models,
                               tags=['nonexistent'])
        self.assertEqual(len(docs), 0)
        # note that giving a tag that exists will return documents but give a large distance
        docs = om.datasets.get('mydocs', document='quick brown',
                               model_store=om.models,
                               tags=['vehicle'])
        self.assertEqual(len(docs), 1)
        self.assertTrue(docs[0]['text'] == 'A fast car zooms by')
        self.assertTrue(docs[0]['distance'] > 0.5)  # assuming a distance threshold
        # filter by max_distance
        docs = om.datasets.get('mydocs', document='quick brown',
                               model_store=om.models,
                               tags=['vehicle'],
                               max_distance=0.1)
        self.assertEqual(len(docs), 0)
        # get all tags
        index = om.datasets.get('mydocs')
        self.assertIsInstance(index, DocumentIndex)
        tags = index.attributes()
        self.assertEqual(tags,
                         {'labels': {'lazy': 1}, 'tags': {'animal': 2, 'lazy': 1, 'vehicle': 1}, 'source': {'': 3}})
        tags = index.attributes(key='tags')
        self.assertEqual(tags, {'tags': {'animal': 2, 'lazy': 1, 'vehicle': 1}})
        labels = index.attributes(key='labels')
        self.assertEqual(labels, {'labels': {'lazy': 1}})

    def test_background_indexing(self):
        om = self.om
        # create a document index
        embedding_model = SimpleEmbeddingModel()
        documents = [
            'The quick brown fox jumps over the lazy dog',
        ]
        embedding_model.fit(documents)
        om.models.put(embedding_model, 'embedding')
        om.datasets.put(self._cnx_str, 'myindex',
                        embedding_model='embedding',
                        replace=True,
                        collection='test',
                        vector_size=embedding_model.dimensions)

        # simulate upload and background indexing
        def simulate_upload_file(fn, index):
            with BytesIO() as fout:
                text = """
                Hello world
                """
                fout.write(text.encode('utf-8'))
                fout.seek(0)
                meta = om.datasets.put(fout, fn, attributes={
                    'index': index
                })
            return meta

        # -- upload
        meta = simulate_upload_file('documents/mydocument', 'myindex')
        # -- run housekeeping, expect pending files to be indexed
        indexed = omega_indexdocuments()
        self.assertEqual(len(indexed), 1)
        # -- run housekeeping again, expect no file to be indexed
        indexed = omega_indexdocuments()
        self.assertEqual(len(indexed), 0)
        # -- check file has been marked indexed
        meta = om.datasets.metadata(meta.name)
        self.assertEqual(meta.attributes.get('indexed'), True)
        # try with multiple files to be indexed
        simulate_upload_file('documents/mydocument', 'myindex')
        simulate_upload_file('documents/otherdocument', 'myindex')
        indexed = omega_indexdocuments()
        self.assertEqual(len(indexed), 2)
        # try with specific files to be indexed
        simulate_upload_file('documents/mydocument', 'myindex')
        simulate_upload_file('documents/otherdocument', 'myindex')
        indexed = omega_indexdocuments(documents=['documents/mydocument'])
        self.assertEqual(len(indexed), 1)
        # try without specific index on document meta data
        simulate_upload_file('documents/mydocument', '')
        with self.assertRaises(AssertionError):
            omega_indexdocuments(documents=['documents/mydocument'])
        indexed = omega_indexdocuments(documents=['documents/mydocument'], index='myindex')
        self.assertEqual(len(indexed), 1)
        meta = om.datasets.metadata('documents/mydocument')
        self.assertTrue(meta.attributes.get('indexed'))
        # check otherdocument has not been indexed
        meta = om.datasets.metadata('documents/otherdocument')
        self.assertFalse(meta.attributes.get('indexed'))
        # check we can use a pattern to index multiple documents at once
        simulate_upload_file('documents/mydocument', 'myindex')
        simulate_upload_file('documents/otherdocument', 'myindex')
        indexed = omega_indexdocuments(documents='documents/*', index='myindex')
        self.assertEqual(len(indexed), 2)

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
