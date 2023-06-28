from omegaml.util import ensure_list
from sklearn.base import BaseEstimator
from sklearn.feature_extraction.text import TfidfVectorizer


class SimpleEmbeddingModel(BaseEstimator):
    """
    A simple text embedding model that uses TF-IDF vectorization to generate
    numerical representations of input documents.

    Attributes:
        vectorizer (TfidfVectorizer): The TF-IDF vectorizer used to transform
            text documents into numerical feature vectors.
    """

    def __init__(self):
        self.vectorizer = TfidfVectorizer(min_df=1)

    def fit(self, documents):
        """
        Fit the TF-IDF vectorizer to the given documents.

        Args:
            documents (list of str): The text documents to use for fitting the
                vectorizer.

        Returns:
            SimpleEmbeddingModel: The fitted model instance.
        """
        self.vectorizer.fit(documents)
        return self

    def embed(self, documents):
        """
        Generate numerical feature vectors for the given documents using the
        fitted TF-IDF vectorizer.

        Args:
            documents (list of str): The text documents to be embedded.

        Returns:
            numpy.ndarray: The embedding vectors for the input documents.
        """
        documents = ensure_list(documents)
        X = self.vectorizer.transform(documents)
        embedding_vectors = X.toarray()
        return embedding_vectors
