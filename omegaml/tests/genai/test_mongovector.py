from omegaml.backends.genai.mongovector import MongoDBVectorStore
from omegaml.tests.genai.test_pgvector import PGVectorDBTests


class MongoVectorDBTests(PGVectorDBTests):
    def initparams(self):
        self._vectordb_cls = MongoDBVectorStore
        self._cnx_str = 'vector+mongodb://localhost:27017/omegaml_test'

    def test_put_get_mocked(self):
        pass


PGVectorDBTests = None  # type: ignore
