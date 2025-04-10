import numpy as np
import unittest
from numpy.testing import assert_allclose
from omegaml.backends.genai.embedding import SimpleEmbeddingModel
from sklearn.feature_extraction.text import TfidfVectorizer


class TestSimpleEmbeddingModel(unittest.TestCase):
    def setUp(self):
        self.model = SimpleEmbeddingModel()
        self.documents = ["This is a sample document.",
                          "Another sample document for testing.",
                          "A third document to test the embedding."]

    def test_fit(self):
        self.model.fit(self.documents)
        self.assertIsInstance(self.model.vectorizer, TfidfVectorizer)

    def test_embed(self):
        self.model.fit(self.documents)
        embeddings = self.model.embed(self.documents)
        self.assertIsInstance(embeddings, np.ndarray)
        self.assertEqual(embeddings.shape, (3, len(self.model.vectorizer.vocabulary_)))
        assert_allclose(embeddings, np.array([
            [0.0, 0.34520501686496574, 0.0, 0.0, 0.5844829010200651, 0.444514311537431, 0.0, 0.0, 0.0, 0.0,
             0.5844829010200651, 0.0],
            [0.5046113401371842, 0.2980315863446099, 0.0, 0.5046113401371842, 0.0, 0.3837699307603192, 0.0,
             0.5046113401371842, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.25537359879528915, 0.4323850887896905, 0.0, 0.0, 0.0, 0.4323850887896905, 0.0, 0.4323850887896905,
             0.4323850887896905, 0.0, 0.4323850887896905]]), rtol=1e-1)

    def test_embed_new_documents(self):
        self.model.fit(self.documents)
        new_documents = ["This is a new document to test.",
                         "Yet another new document."]
        embeddings = self.model.embed(new_documents)
        self.assertIsInstance(embeddings, np.ndarray)
        self.assertEqual(embeddings.shape, (2, len(self.model.vectorizer.vocabulary_)))
        assert_allclose(embeddings, np.array(
            [[0.0, 0.2832169249871526, 0.0, 0.0, 0.479527938028855, 0.0, 0.479527938028855, 0.0, 0.0, 0.0,
              0.479527938028855, 0.479527938028855],
             [0.8610369959439764, 0.5085423203783267, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]), rtol=1e-1)


if __name__ == '__main__':
    unittest.main()
