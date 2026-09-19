import json
import unittest
from pathlib import Path

import omegaml
from omegaml import Omega
from omegaml.backends.genai import GenAIBaseBackend, GenAIModelHandler
from omegaml.backends.genai.models.conversation import ConversationModelBackend
from omegaml.client.auth import OmegaRestApiAuth
from omegaml.client.util import subdict
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
        self.om.models.register_backend(ConversationModelBackend.KIND, ConversationModelBackend)

    @property
    def _headers(self):
        return {}

    def test_model_completion(self):
        """Test the /v1/model/complete API endpoint."""
        self._setup_chat_model()
        # get a single response
        resp = self.client.put(
            '/api/v1/model/mymodel/complete',
            json={
                "prompt": "hello",
            },
            auth=self.auth,
            headers=self._headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'application/json')
        self.assertEqual(
            resp.json,
            {
                'model': 'mymodel',
                'result': {
                    'model': 'mymodel',
                    'content': 'hello',
                },
                'resource_uri': 'mymodel',
            },
        )
        # stream
        resp = self.client.put(
            '/api/v1/model/mymodel/complete',
            json={
                "prompt": "hello",
                "stream": True,
            },
            auth=self.auth,
            headers=self._headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'text/event-stream')
        # we get SSE-formated responses
        # -- data: { ... } # every streamed response is a json object
        # -- https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events
        data = [json.loads(d.split(b'data: ')[-1]) if d.startswith(b'data:') else d for d in resp.iter_encoded()]
        self.assertEqual(len(data), len('hello'))
        # FIXME the 'result' should really be 'content' (for consistency with OpenAI?)
        self.assertEqual(
            data[-1],
            {
                'model': 'mymodel',
                'result': {'content': 'hello', 'delta': 'o', 'model': 'mymodel'},
                'resource_uri': 'mymodel',
            },
        )

    def test_model_embedding(self):
        """Test the /v1/model/embed API endpoint."""
        om = self.om

        self._create_embedding_model()
        # get a single response
        resp = self.client.put(
            '/api/v1/model/myembedding/embed',
            json={"documents": ["hello", "world"]},
            auth=self.auth,
            headers=self._headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'application/json')
        self.assertEqual(
            resp.json,
            {
                'model': 'myembedding',
                'result': {'model': 'myembedding', 'embeddings': [[1.0] * 10] * 2},
                'resource_uri': 'myembedding',
            },
        )

    def test_openai_embeddings(self):
        self._create_embedding_model()
        # get a single response
        resp = self.client.post(
            '/api/openai/v1/embeddings',
            json={"model": 'myembedding', "documents": ["hello", "world"]},
            auth=self.auth,
            headers=self._headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'application/json')
        self.assertEqual(
            resp.json,
            {
                'model': 'myembedding',
                'embeddings': [[1.0] * 10] * 2,
                'resource_uri': 'myembedding',
            },
        )

    def test_openai_chat_completions(self):
        self._setup_chat_model()
        # openai api
        # -- non-streaming
        resp = self.client.post(
            '/api/openai/v1/chat/completions',
            json={
                "model": "mymodel",
                "messages": [
                    {
                        "role": "user",
                        "content": "hello",
                    }
                ],
            },
            auth=self.auth,
            headers=self._headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'application/json')
        self.assertEqual(
            resp.json,
            {
                'model': 'mymodel',
                'content': 'hello',
                'resource_uri': 'mymodel',
            },
        )
        # -- streaming
        resp = self.client.post(
            '/api/openai/v1/chat/completions',
            json={
                "model": "mymodel",
                "messages": [
                    {
                        "role": "user",
                        "content": "hello",
                    }
                ],
                "stream": True,
            },
            auth=self.auth,
            headers=self._headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'text/event-stream')
        data = [json.loads(d.split(b'data: ')[-1]) if d.startswith(b'data:') else d for d in resp.iter_encoded()]
        self.assertEqual(len(data[-1]['content']), len('hello'))
        self.assertEqual(
            subdict(data[-1], ['content', 'delta']),
            {
                'content': 'hello',
                'delta': 'o',
            },
        )

    def test_openai_audio_transcribe(self):
        self._setup_voice_model()
        wav_file_path = Path(omegaml.__file__).parent / 'example/demo/multimodal/resources/sample.wav'
        self.client.is_json = False
        # TODO: use an actual model to test end to end (whisper-1 does not exist)
        resp = self.client.post(
            '/api/openai/v1/audio/transcriptions',
            data={
                'file': (wav_file_path, 'test.wav'),
                'model': 'voicemodel',
            },
            content_type='multipart/form-data',
            auth=self.auth,
            headers=self._headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'application/json')
        self.assertEqual(
            resp.json,
            {
                'model': 'voicemodel',
                'text': 'hello world',
                'resource_uri': 'voicemodel',
            },
        )

    def test_openai_audio_transcribe_stream(self):
        self._setup_voice_model()
        wav_file_path = Path(omegaml.__file__).parent / 'example/demo/multimodal/resources/sample.wav'
        self.client.is_json = False
        resp = self.client.post(
            '/api/openai/v1/audio/transcriptions',
            data={
                'file': (wav_file_path, 'test.wav'),
                'model': 'voicemodel',
                'stream': True,
            },
            content_type='multipart/form-data',
            auth=self.auth,
            headers=self._headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'text/event-stream')
        data = [json.loads(d.split(b'data: ')[-1]) if d.startswith(b'data:') else d for d in resp.iter_encoded()]
        self.assertEqual(''.join(d['delta'] for d in data), 'hello world')
        for d, c in zip(data, 'hello world'):
            self.assertEqual(
                subdict(d, ['delta', 'type']),
                {
                    'delta': c,
                    'type': 'transcript.text.delta',
                },
            )

    def test_openai_audio_speech(self):
        self._setup_voice_model()
        wav_file_path = Path(omegaml.__file__).parent / 'example/demo/multimodal/resources/sample.wav'
        self.client.is_json = False
        # TODO: use an actual model to test end to end (whisper-1 does not exist)
        resp = self.client.post(
            '/api/openai/v1/audio/speech',
            json={
                'model': 'voicemodel',
                'input': 'hello world',
            },
            auth=self.auth,
            headers=self._headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'application/json')
        self.assertEqual(
            resp.json,
            {
                'model': 'voicemodel',
                'dataset': './audio/speech',
                'resource_uri': 'voicemodel',
            },
        )

    def _create_embedding_model(self):
        # test save and restore
        class MyEmbeddingModel(GenAIModelHandler):
            def embed(self, documents, **kwargs):
                return {'model': 'myembedding', 'embeddings': [[1.0] * 10] * len(documents)}

        self.om.models.put(MyEmbeddingModel, 'myembedding', replace=True)

    def _setup_chat_model(self):
        # test save and restore
        class MyModel(GenAIModelHandler):
            def complete(self, prompt, messages=None, conversation_id=None, data=None, stream=False, **kwargs):
                prompt = prompt or '\n'.join([m['content'] for m in messages if m['role'] == 'user'])
                if stream:

                    def stream_result():
                        for i, c in enumerate(prompt):
                            yield {'model': 'mymodel', 'delta': c, 'content': prompt[:i] + c}

                    return stream_result()
                return {
                    'model': 'mymodel',
                    'content': prompt,
                }

        self.om.models.put(MyModel, 'mymodel', replace=True)

    def _setup_voice_model(self):
        # test save and restore
        class VoiceModel(GenAIModelHandler):
            def transcribe(self, audio, response_format='json', stream=False, **kwargs):
                resp = None
                if response_format == 'json':
                    resp = {'text': 'hello world'}
                    if stream:

                        def stream_result(content):
                            for c in content:
                                yield {
                                    'type': 'transcript.text.delta',
                                    'delta': c,
                                }

                        resp = stream_result(resp['text'])
                return resp

            def speech(self, text, **kwargs):
                return {
                    'dataset': './audio/speech',
                }

        self.om.models.put(VoiceModel, 'voicemodel', replace=True)


if __name__ == '__main__':
    unittest.main()
