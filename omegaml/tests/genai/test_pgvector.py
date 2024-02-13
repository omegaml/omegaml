from unittest import TestCase

from omegaml.backends.genai.pgvector import PGVectorBackend
from omegaml.tests.util import OmegaTestMixin


class GenAIModelTests(OmegaTestMixin, TestCase):
    def setUp(self):
        from omegaml import Omega
        self.om = Omega()
        self.om.models.register_backend(PGVectorBackend.KIND, PGVectorBackend)
        self.clean()

    def test_put_get(self):
        om = self.om
        meta = om.datasets.put('pgvector://postgres:test@localhost:5432/postgres', 'mydocs',
                               replace=True,
                               collection='test',
                               vector_size=3)
        self.assertEqual(meta.kind, PGVectorBackend.KIND)
        documents = [
            # (chunk, embedding)
            ('my text', [1, 2, 3]),
            ('my other text', [99, 100, 200]),
        ]
        om.datasets.put(documents, 'mydocs')
        chunks = om.datasets.get('mydocs', obj=[3, 0, 0])
        self.assertEqual(chunks[0]['text'], 'my text')
        chunks = om.datasets.get('mydocs', obj=[99, 150, 150])
        self.assertEqual(chunks[0]['text'], 'my other text')
        print(meta.kind_meta)
