from unittest import TestCase

from omegaml.backends.genai.pgvector import PGVectorBackend
from omegaml.tests.util import OmegaTestMixin


class GenAIModelTests(OmegaTestMixin, TestCase):
    def setUp(self):
        from omegaml import Omega
        self.om = Omega()
        self.clean()
        self.om.models.register_backend(PGVectorBackend.KIND, PGVectorBackend)

    def test_put_get(self):
        om = self.om
        meta = om.datasets.put('pgvector://postgres:test@localhost:5432/postgres', 'mydocs', table='test', vector_size=3)
        self.assertEqual(meta.kind, PGVectorBackend.KIND)
        documents = [
            # (chunk, embedding)
            ('my text', [1, 2, 3]),
        ]
        om.datasets.put(documents, 'mydocs')
        chunks = om.datasets.get('mydocs', obj=[3, 2, 1])
        print(chunks)
        print(meta.kind_meta)
