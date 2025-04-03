import json
import unittest
import warnings
from omegaml import Omega
from omegaml.backends.genai.models import GenAIBaseBackend, GenAIModelHandler
from omegaml.backends.genai.textmodel import TextModelBackend
from omegaml.client.auth import OmegaRestApiAuth
from omegaml.server import restapi
from omegaml.tests.core.restapi.util import RequestsLikeTestClient
from omegaml.tests.util import OmegaTestMixin


class GenAITestCase(OmegaTestMixin, unittest.TestCase):
    def setUp(self):
        # ignore pymongo resource warnings (due to completion async stream)
        warnings.filterwarnings('ignore', category=ResourceWarning, module=r'minibatch|omegaml')
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

    def test_completion(self):
        om = self.om

        # test save and restore
        class MyModel(GenAIModelHandler):
            def complete(self, prompt, messages=None, conversation_id=None,
                         data=None, stream=False, **kwargs):
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

        self.om.models.put(MyModel, 'mymodel')
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


if __name__ == '__main__':
    unittest.main()
