import json
import unittest

from omegaml import Omega
from omegaml.backends.genai.models import GenAIBaseBackend, GenAIModelHandler
from omegaml.backends.genai.textmodel import TextModelBackend
from omegaml.client.auth import OmegaRestApiAuth
from omegaml.server import restapi
from omegaml.tests.core.restapi.util import RequestsLikeTestClient
from omegaml.tests.util import OmegaTestMixin


class GenAITestCase(OmegaTestMixin, unittest.TestCase):
    def setUp(self):
        app = restapi.create_app()
        self.client = RequestsLikeTestClient(app, is_json=True)
        self.om = Omega()
        self.auth = OmegaRestApiAuth('user', 'pass')
        self.clean()
        self.om.models.register_backend(GenAIBaseBackend.KIND, GenAIBaseBackend)
        self.om.models.register_backend(TextModelBackend.KIND, TextModelBackend)

    @property
    def _headers(self):
        return {}

    def test_model_completion(self):
        """ Test the /v1/model/complete API endpoint."""
        self._setup_chat_model()
        # get a single response
        resp = self.client.put('/api/v1/model/mymodel/complete', json={
            "prompt": "hello",
        }, auth=self.auth, headers=self._headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'application/json')
        self.assertEqual(resp.json, {'model': 'mymodel',
                                     'result': {
                                         'model': 'mymodel',
                                         'content': 'hello'
                                     },
                                     'resource_uri': 'mymodel'})
        # stream
        resp = self.client.put('/api/v1/model/mymodel/complete', json={
            "prompt": "hello",
            "stream": True,
        }, auth=self.auth, headers=self._headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'text/event-stream')
        # we get SSE-formated responses
        # -- data: { ... } # every streamed response is a json object
        # -- https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events
        data = list(map(lambda d: json.loads(d.split(b'data: ')[-1]) if d.startswith(b'data:') else d,
                        resp.iter_encoded()))
        self.assertEqual(len(data), len('hello'))
        # FIXME the 'result' should really be 'content' (for consistency with OpenAI?)
        self.assertEqual(data[-1],
                         {'model': 'mymodel',
                          'result': {'content': 'hello', 'delta': 'o', 'model': 'mymodel'},
                          'resource_uri': 'mymodel'})

    def test_model_embedding(self):
        """ Test the /v1/model/embed API endpoint."""
        om = self.om

        self._create_embedding_model()
        # get a single response
        resp = self.client.put('/api/v1/model/myembedding/embed', json={
            "documents": ["hello", "world"],
        }, auth=self.auth, headers=self._headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'application/json')
        self.assertEqual(resp.json, {'model': 'myembedding',
                                     'result': {
                                         'model': 'myembedding',
                                         'embeddings': [[1.0] * 10] * 2,
                                     },
                                     'resource_uri': 'myembedding'})

    def test_openai_embeddings(self):
        self._create_embedding_model()
        # get a single response
        resp = self.client.post('/api/openai/v1/embeddings', json={
            "model": 'myembedding',
            "documents": ["hello", "world"],
        }, auth=self.auth, headers=self._headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'application/json')
        self.assertEqual(resp.json, {
            'model': 'myembedding',
            'embeddings': [[1.0] * 10] * 2,
            'resource_uri': 'myembedding',
        })

    def test_openai_chat_completions(self):
        self._setup_chat_model()
        # openai api
        # -- non-streaming
        resp = self.client.post('/api/openai/v1/chat/completions', json={
            "model": "mymodel",
            "messages": [
                {"role": "user", "content": "hello"},
            ],
        }, auth=self.auth, headers=self._headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'application/json')
        self.assertEqual(resp.json, {
            'model': 'mymodel',
            'content': 'hello',
            'resource_uri': 'mymodel',
        })
        # -- streaming
        resp = self.client.post('/api/openai/v1/chat/completions', json={
            "model": "mymodel",
            "messages": [
                {"role": "user", "content": "hello"},
            ],
            "stream": True,
        }, auth=self.auth, headers=self._headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'text/event-stream')
        data = list(map(lambda d: json.loads(d.split(b'data: ')[-1]) if d.startswith(b'data:') else d,
                        resp.iter_encoded()))
        self.assertEqual(len(data), len('hello'))
        # FIXME the 'result' should really be 'content' (for consistency with OpenAI?)
        self.assertEqual(data[-1], {
            'model': 'mymodel',
            'content': 'hello', 'delta': 'o',
            'resource_uri': 'mymodel',
        })

    def _create_embedding_model(self):
        # test save and restore
        class MyEmbeddingModel(GenAIModelHandler):
            def embed(self, documents, **kwargs):
                return {
                    'model': 'myembedding',
                    'embeddings': [[1.0] * 10] * len(documents),
                }

        self.om.models.put(MyEmbeddingModel, 'myembedding', replace=True)

    def _setup_chat_model(self):
        # test save and restore
        class MyModel(GenAIModelHandler):
            def complete(self, prompt, messages=None, conversation_id=None,
                         data=None, stream=False, **kwargs):
                prompt = prompt or '\n'.join([m['content'] for m in messages if m['role'] == 'user'])
                if stream:
                    def stream_result():
                        for i, c in enumerate(prompt):
                            yield {
                                'model': 'mymodel',
                                'delta': c,
                                'content': prompt[:i] + c,
                            }

                    return stream_result()
                return {
                    'model': 'mymodel',
                    'content': prompt,
                }

        self.om.models.put(MyModel, 'mymodel', replace=True)


if __name__ == '__main__':
    unittest.main()
