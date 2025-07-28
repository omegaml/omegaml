from omegaml.backends.genai.inmemory import InMemoryVectorStore
from omegaml.tests.genai.test_pgvector import PGVectorDBTests


class InMemoryVectorDBTests(PGVectorDBTests):
    def initparams(self):
        self._vectordb_cls = InMemoryVectorStore
        self._cnx_str = 'vector+memory://'

    def test_put_get_mocked(self):
        pass


PGVectorDBTests = None  # type: ignore
