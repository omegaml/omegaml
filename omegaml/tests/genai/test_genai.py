from unittest import TestCase, mock

from omegaml.backends.genai.models import GenAIBaseBackend, GenAIModel, virtual_genai, GenAIModelHandler
from omegaml.backends.genai.openai import OpenAIModelBackend, OpenAIModel
from omegaml.client.util import AttrDict
from omegaml.tests.util import OmegaTestMixin


class GenAIModelTests(OmegaTestMixin, TestCase):
    def setUp(self):
        from omegaml import Omega
        self.om = Omega()
        self.clean()
        self.om.models.register_backend(GenAIBaseBackend.KIND, GenAIBaseBackend)
        self.om.models.register_backend(OpenAIModelBackend.KIND, OpenAIModelBackend)

    def test_put_get_model_handler(self):
        # test save and restore
        class MyModel(GenAIModelHandler):
            def complete(self, prompt, messages=None, conversation_id=None,
                         data=None, **kwargs):
                return prompt

        meta = self.om.models.put(MyModel, 'mymodel')
        del MyModel  # ensure we can restore from scratch
        model = self.om.models.get('mymodel')
        self.assertEqual(meta.kind, GenAIBaseBackend.KIND)
        self.assertIsInstance(model, GenAIModel)
        # run complete directly
        X = {
            'prompt': 'hello',
        }
        self.om.datasets.put(X, 'X')
        result = model.complete(X['prompt'])
        self.assertEqual(result, 'hello')
        # run it via runtime
        # -- direct input
        result = self.om.runtime.model('mymodel').complete(X).get()
        self.assertEqual(result, 'hello')
        # run it via runtime
        # -- dataset input
        result = self.om.runtime.model('mymodel').complete('X').get()
        self.assertEqual(result, 'hello')

    def test_put_get_virtualfn_handler(self):
        @virtual_genai
        def mymodel(prompt, messages=None, method=None, **kwargs):
            return method, prompt

        # test save and restore
        meta = self.om.models.put(mymodel, 'mymodel')
        del mymodel  # ensure we can restore from scratch
        model = self.om.models.get('mymodel')
        self.assertEqual(meta.kind, GenAIBaseBackend.KIND)
        self.assertTrue(hasattr(model, '_omega_virtual_genai'))
        # run complete directly
        X = {
            'prompt': 'hello',
        }
        self.om.datasets.put(X, 'X')
        result = model.complete(X['prompt'])
        self.assertEqual(result, ('complete', 'hello'))  # method, prompt
        # run it via runtime
        # -- direct input
        result = self.om.runtime.model('mymodel').complete(X).get()
        self.assertEqual(result, ('complete', 'hello'))  # method, prompt
        # run it via runtime
        # -- dataset input
        result = self.om.runtime.model('mymodel').complete('X').get()
        self.assertEqual(result, ('complete', 'hello'))  # method, prompt

    def test_openai_put_get_default(self):
        # test save and restore
        meta = self.om.models.put('openai://localhost/mymodel', 'mymodel')
        self.assertEqual(meta.kind, OpenAIModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'https://localhost:443')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')
        model = self.om.models.get('mymodel')
        self.assertIsInstance(model, OpenAIModel)
        # replace
        meta = self.om.models.put('openai://localhost;model=mymodel', 'mymodel', replace=True)
        self.assertEqual(meta.kind, OpenAIModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'https://localhost:443')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')
        # replace
        meta = self.om.models.put('openai://localhost/v1;model=mymodel', 'mymodel', replace=True)
        self.assertEqual(meta.kind, OpenAIModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'https://localhost:443/v1')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')

    def test_openai_http_scheme(self):
        # test save and restore
        meta = self.om.models.put('openai+http://localhost/mymodel', 'mymodel')
        self.assertEqual(meta.kind, OpenAIModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'http://localhost:80')
        model = self.om.models.get('mymodel')
        self.assertIsInstance(model, OpenAIModel)
        # replace
        meta = self.om.models.put('openai+http://localhost:8080/mymodel', 'mymodel', replace=True)
        self.assertEqual(meta.kind, OpenAIModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'http://localhost:8080')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')

    @mock.patch('omegaml.backends.genai.openai.OpenAI')
    def test_openai_calling(self, OpenAI):
        meta = self.om.models.put('openai+http://localhost/mymodel', 'mymodel')
        model = self.om.models.get('mymodel')
        # mock openai call
        openai_response = AttrDict({
            'choices': [AttrDict({
                'message': AttrDict({
                    'role': 'assistant',
                    'content': 'hello how are you',
                })})]
        })
        model.client.chat.completions.create.return_value = openai_response
        # check call to openai would be ok
        result = model.complete('hello')
        model.client.chat.completions.create.assert_called()
        kwargs = model.client.chat.completions.create.call_args.kwargs
        self.assertIn('model', kwargs)
        self.assertIn('messages', kwargs)
        model = kwargs['model']
        self.assertEqual(model, 'mymodel')
        self.assertEqual(model, 'mymodel')
        messages = kwargs['messages']
        # check all conversation ids are the same
        conversation_id = None
        for message in messages:
            if conversation_id is not None:
                self.assertEqual(message['conversation_id'], conversation_id)
            else:
                conversation_id = message['conversation_id']
        # check conversation is returned as expected
        self.assertEqual(result['role'], 'assistant')
        self.assertEqual(result['content'], 'hello how are you')
        self.assertEqual(result['conversation_id'], conversation_id)
