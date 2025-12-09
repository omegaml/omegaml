from unittest import TestCase

from flask import url_for

from omegaml.backends.genai.textmodel import TextModel
from omegaml.server.app import create_app
from omegaml.tests.util import OmegaTestMixin


class PromptsViewTest(OmegaTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()
        globals().update(url_for=self.url_for)

    def url_for(self, endpoint, **kwargs):
        from flask import url_for
        with self.app.test_request_context():
            return url_for(endpoint, **kwargs)

    def test_prompt_save(self):
        om = self.om
        om.models.put('openai+http://localhost/mymodel', 'llms/mymodel',
                      prompt='you are not very helpful')
        # create a new prompt based on an existing model
        resp = self.client.post(url_for('omega-ai.prompts_api_save_prompt',
                                        name='prompts/myprompt'),
                                json={
                                    'model': 'llms/mymodel',
                                    'prompt': 'you are a very helpful assistant',
                                })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('prompts/myprompt', om.models.list())
        meta = om.models.metadata('prompts/myprompt')
        self.assertEqual(meta.attributes['model'], 'llms/mymodel')
        self.assertEqual(meta.attributes['prompt'], 'you are a very helpful assistant')
        prompt = om.models.get('prompts/myprompt')
        self.assertIsInstance(prompt, TextModel)
        self.assertEqual(prompt.model, 'mymodel')
        self.assertEqual(prompt.prompt, 'you are a very helpful assistant')
        # update the prompt
        resp = self.client.post(url_for('omega-ai.prompts_api_save_prompt',
                                        name='prompts/myprompt'),
                                json={
                                    'model': 'llms/mymodel',
                                    'prompt': 'you are a really very helpful assistant',
                                })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('prompts/myprompt', om.models.list())
        meta = om.models.metadata('prompts/myprompt')
        self.assertEqual(meta.attributes['model'], 'llms/mymodel')
        self.assertEqual(meta.attributes['prompt'], 'you are a really very helpful assistant')
        prompt = om.models.get('prompts/myprompt')
        self.assertIsInstance(prompt, TextModel)
        self.assertEqual(prompt.model, 'mymodel')
        self.assertEqual(prompt.prompt, 'you are a really very helpful assistant')
