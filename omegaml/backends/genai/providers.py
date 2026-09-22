import re
from urllib.parse import urljoin

import requests
from openai import OpenAI

from omegaml.util import ensure_list


class Provider:
    URL_REGEX = None

    def __init__(self, api_key, base_url, model=None, tracking=None, **kwargs):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.tracking = tracking

    def embed(self, documents, dimensions=None, **kwargs):
        raise NotImplementedError

    def complete(self, model, messages, stream=False, **kwargs):
        raise NotImplementedError

    @classmethod
    def match_url(cls, url):
        return re.match(cls.URL_REGEX, str(url)) if cls.URL_REGEX else False


class OpenAIProvider(Provider):
    URL_REGEX = r'https?://(api\.openai\.com|localhost)(:\d+)?/.*'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model = self.model

    def embed(self, documents, dimensions=None, model=None, **kwargs):
        documents = ensure_list(documents)
        response = self.client.embeddings.create(
            model=model or self.model, input=documents, dimensions=dimensions, encoding_format="float"
        )
        return response.to_dict()

    def complete(self, messages, stream=False, model=None, **kwargs):
        if stream:
            # https://community.openai.com/t/usage-stats-now-available-when-using-streaming-with-the-chat-completions-api-or-completions-api/738156
            kwargs.setdefault('stream_options', {"include_usage": True})
        response = self.client.chat.completions.create(
            model=model or self.model, messages=messages, stream=stream, **kwargs
        )
        return response.to_dict() if not stream else (chunk.to_dict() for chunk in response)


class JinaEmbeddingsProvider(Provider):
    URL_REGEX = r'https?://(api\.jina\.ai)(:\d+)?/.*'

    def embed(self, documents, dimensions=None, model=None, **kwargs):
        """Embed documents using Jina AI's embedding service.

        Args:
            documents (list): List of documents to embed.
            dimensions (int): Number of dimensions to embed to.
            model (str): Model name to use for embedding.

        Returns:
            list: List of embeddings as list[list[float, ...]].
        """
        # see https://jina.ai/embeddings
        documents = ensure_list(documents)
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'}
        url = urljoin(self.base_url, 'embeddings')
        resp = requests.post(
            url, headers=headers, json={'model': self.model, 'input': [{'text': doc} for doc in documents]}
        )
        assert resp.status_code == 200, f'Error {resp.status_code} calling {url}: {resp.text}'
        response = resp.json()
        return response


class AnythingLLMProvider(Provider):
    URL_REGEX = r'https?://(api\.anythingllm\.com|localhost:(3001)+|anythingllm\.com)/.*'

    def embed(self, documents, dimensions=None, **kwargs):
        """Embed documents

        Args:
            documents (list): list of documents to embed
            dimensions (int): number of dimensions to embed to

        Returns:
            list: list of embeddings as list[list[float, ...]]
        """
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'}
        url = urljoin(self.base_url, 'embeddings')
        documents = ensure_list(documents)
        resp = requests.post(url, headers=headers, json={'inputs': documents, 'model': self.model})
        assert resp.status_code == 200, f'Error {resp.status_code} calling {url}: {resp.text}'
        response = resp.json()
        return response

    def complete(self, messages, stream=False, **kwargs):
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'}
        url = f'{self.base_url}/chat/completions'
        resp = requests.post(url, headers=headers, json={'messages': messages, 'model': self.model, 'stream': stream})
        return resp.json()


class OllamaProvider(Provider):
    URL_REGEX = r'https?://(api\.ollama\.com|localhost)(:\d+)?/.*'

    def embed(self, documents, dimensions=None, **kwargs):
        """Embed documents using Ollama's embedding service.

        Args:
            documents (list): List of documents to embed.
            dimensions (int): Number of dimensions to embed to.

        Returns:
            list: List of embeddings as list[list[float, ...]].
        """
        # see https://ollama.com/docs/api/embeddings
        documents = ensure_list(documents)
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'}
        url = urljoin(self.base_url, 'embeddings')
        resp = requests.post(url, headers=headers, json={'model': self.model, 'input': documents})
        assert resp.status_code == 200, f'Error {resp.status_code} calling {url}: {resp.text}'
        response = resp.json()
        return response


PROVIDERS = {
    'openai': OpenAIProvider,
    'anythingllm': AnythingLLMProvider,
    'jina': JinaEmbeddingsProvider,
    'default': OpenAIProvider,
}
