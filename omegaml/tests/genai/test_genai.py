from unittest import TestCase, mock

import inspect
from omegaml.backends.genai import SimpleEmbeddingModel
from omegaml.backends.genai.models import GenAIBaseBackend, GenAIModel, virtual_genai, GenAIModelHandler
from omegaml.backends.genai.mongovector import MongoDBVectorStore
from omegaml.backends.genai.textmodel import TextModelBackend, TextModel
from omegaml.client.util import AttrDict, dotable, subdict
from omegaml.tests.util import OmegaTestMixin
from types import FunctionType


class GenAIModelTests(OmegaTestMixin, TestCase):
    """ testing gen ai features

    Notes:
        - Testing omega-ml's orchestration of gen ai model calls, not actual models
        - Using mock model responses
    """

    def setUp(self):
        from omegaml import Omega
        self.om = Omega()
        self.clean()
        # self.om.models.register_backend(GenAIBaseBackend.KIND, GenAIBaseBackend)
        self.om.models.register_backend(TextModelBackend.KIND, TextModelBackend)
        self.om.models.register_backend(MongoDBVectorStore.KIND, MongoDBVectorStore)

    def test_put_get_model_handler(self):
        # test save and restore
        class MyModel(GenAIModelHandler):
            def complete(self, prompt, messages=None, conversation_id=None,
                         data=None, **kwargs):
                return prompt

        meta = self.om.models.put(MyModel, 'mymodel')
        self.assertEqual(meta.kind, GenAIBaseBackend.KIND)
        del MyModel  # ensure we can restore from scratch
        model = self.om.models.get('mymodel')
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
        self.assertEqual(meta.kind, TextModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'https://localhost:443')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')
        model = self.om.models.get('mymodel')
        self.assertIsInstance(model, TextModel)
        # replace
        meta = self.om.models.put('openai://localhost;model=mymodel', 'mymodel', replace=True)
        self.assertEqual(meta.kind, TextModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'https://localhost:443')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')
        # replace
        meta = self.om.models.put('openai://localhost/v1;model=mymodel', 'mymodel', replace=True)
        self.assertEqual(meta.kind, TextModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'https://localhost:443/v1')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')

    def test_openai_http_scheme(self):
        # test save and restore
        meta = self.om.models.put('openai+http://localhost/mymodel', 'mymodel')
        self.assertEqual(meta.kind, TextModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'http://localhost:80')
        model = self.om.models.get('mymodel')
        self.assertIsInstance(model, TextModel)
        # replace
        meta = self.om.models.put('openai+http://localhost:8080/mymodel', 'mymodel', replace=True)
        self.assertEqual(meta.kind, TextModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'http://localhost:8080')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')

    @mock.patch('omegaml.backends.genai.textmodel.OpenAIProvider')
    def test_openai_calling(self, OpenAIProvider):
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
        model.provider = OpenAIProvider
        model.provider.complete.return_value = openai_response
        # check call to openai would be ok
        result = model.complete('hello')
        model.provider = OpenAIProvider
        model.provider.complete.assert_called()
        kwargs = model.provider.complete.call_args.kwargs
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

    @mock.patch('omegaml.backends.genai.textmodel.OpenAIProvider')
    def test_openai_stream(self, OpenAIProvider):
        meta = self.om.models.put('openai+http://localhost/mymodel', 'mymodel')
        model = self.om.models.get('mymodel')
        # mock openai call
        # -- simulate tokenized responses, one character at a time
        openai_responses = [AttrDict({
            'choices': [AttrDict({
                'delta': AttrDict({
                    'role': 'assistant',
                    'content': c,
                })})]
        }) for c in 'hello how are you']
        model.provider = OpenAIProvider
        model.provider.complete.return_value = openai_responses
        # check call to openai returns a generator to stream
        result = model.complete('hello', stream=True)
        self.assertTrue(inspect.isgenerator(result))
        for chunk in result:
            self.assertIn('role', chunk)
            self.assertIn('delta', chunk)
            self.assertIn('content', chunk)
        # check final conversation is returned as expected
        self.assertEqual(chunk['content'], 'hello how are you')
        # check completions endpoint was called ok
        # -- note it's a (mocked) streaming call, so only called once
        self.assertEqual(model.provider.complete.call_count, 1)
        kwargs = model.provider.complete.call_args.kwargs
        self.assertIn('model', kwargs)
        self.assertIn('messages', kwargs)
        model = kwargs['model']
        self.assertEqual(model, 'mymodel')

    @mock.patch('omegaml.backends.genai.textmodel.OpenAIProvider')
    def test_openai_embedding(self, OpenAIProvider):
        meta = self.om.models.put('openai+http://localhost/mymodel', 'mymodel')
        model = self.om.models.get('mymodel')
        # mock openai call
        openai_responses = {
            "object": "list",
            "model": "mymodel",
            "usage": {
                "total_tokens": 1,
                "prompt_tokens": 1,
            },
            "data": [{
                "object": "embedding",
                "embedding": [1, 2, 3],
                "index": 0,
            }],
        }
        model.provider = OpenAIProvider
        model.provider.embed.return_value = openai_responses
        # check call to openai returns a generator to stream
        result = model.embed('the quick brown fox jumps')
        self.assertEqual(result, openai_responses)

    def test_tool_function(self):
        om = self.om

        def weather():
            return 'sunny'

        om.models.put(weather, 'tools/weather')
        toolfn = om.models.get('tools/weather')
        self.assertTrue(toolfn is not weather)
        del weather
        toolfn = om.models.get('tools/weather')
        self.assertIsInstance(toolfn, FunctionType)
        self.assertEqual(toolfn(), 'sunny')

    @mock.patch('omegaml.backends.genai.textmodel.OpenAIProvider')
    def test_tool_use(self, OpenAIProvider):
        om = self.om

        # define a tool
        def weather():
            return 'sunny'

        om.models.put(weather, 'tools/weather')
        # check model definition includes tools
        meta = om.models.put('openai+http://localhost/mymodel', 'mymodel',
                             tools=['weather'])
        self.assertEqual(meta.attributes['tools'], ['weather'])
        # check model triggers tools
        model = om.models.get('mymodel')
        # mock openai call
        # -- Ref: https://platform.openai.com/docs/api-reference/chat/get
        # -- the model's response to initial prompt (calling a tool)
        openai_response_to_call_tool = dotable({
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        'tool_calls': [{
                            'id': "call_tool_1",
                            "type": "function",
                            "function": {
                                "name": "weather",
                                "arguments": "{}",
                            }}]
                    }
                }
            ]
        })
        # -- the model's response upon receiving tool results
        openai_response_to_tool_result = dotable({
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "the weather is sunny",
                    }
                }
            ]
        })
        # the streamed response to call tools
        openai_response_to_call_tool_stream = dotable({
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": None,
                        'tool_calls': [{
                            'id': "call_tool_1",
                            "type": "function",
                            "function": {
                                "name": "weather",
                                "arguments": "{}",
                            }}]
                    }
                }
            ]
        })
        model.provider = OpenAIProvider
        model.provider.complete.side_effect = [
            # first, without tool use
            openai_response_to_call_tool,
            # then, with tool use (no streamed)
            openai_response_to_call_tool,
            openai_response_to_tool_result,
            # then, with tool use (streamed)
            [openai_response_to_call_tool_stream],
            openai_response_to_tool_result,
        ]
        # prompt to call a tools, do not use tools
        # -- expect the model to respond by suggesting a tool_call
        result = model.complete('what is the weather like?', use_tools=False)
        self.assertEqual(subdict(result, ['role', 'content', 'tool_calls']),
                         {'role': 'assistant',
                          'content': None,
                          'tool_calls': [{'id': 'call_tool_1', 'type': 'function',
                                          'function': {'name': 'weather', 'arguments': '{}'}}]},
                         )
        # same prompt, now ask tool use
        # -- tool is used and model is shown tool output
        result = model.complete('what is the weather like?', use_tools=True)
        self.assertEqual(subdict(result, ['role', 'content', 'tool_calls', 'tool_results']),
                         {'content': 'the weather is sunny', 'role': 'assistant'})
        # stream result
        results = list(model.complete('what is the weather like?', use_tools=True, stream=True))
        self.assertTrue(len(results) > 0)
        self.assertEqual(subdict(results[0], ['role', 'content']),
                         {'content': 'the weather is sunny', 'role': 'assistant'})
        self.assertEqual(subdict(results[0]['intermediate_results'], ['tool_calls', 'tool_prompts']),
                         {'tool_calls': [{'id': 'call_tool_1', 'type': 'function',
                                          'function': {'name': 'weather', 'arguments': '{}'}}],
                          'tool_prompts': [{'role': 'tool', 'tool_call_id': 'call_tool_1', 'content': 'sunny'}]})

    @mock.patch('omegaml.backends.genai.textmodel.OpenAIProvider')
    def test_documents_use(self, OpenAIProvider):
        om = self.om
        # prepare embedding model
        documents = [
            'the quick brown fox jumps over the lazy dog',
            'the slow white dog slogs along the white lane',
        ]
        embedding_model = SimpleEmbeddingModel()
        embedding_model.fit(documents)
        om.models.put(embedding_model, 'embedding')
        # store documents to vector db
        om.datasets.put('vector://', 'documents', embedding_model='embedding')
        om.datasets.put(documents, 'documents', model_store=om.models)
        # prepare llm that uses documents
        meta = om.models.put('openai+http://localhost/mymodel', 'mymodel',
                             documents='documents', template='system documents: {context}')
        model = om.models.get('mymodel', data_store=om.datasets)
        # mock model provider response
        # -- we test our TextModel(GenAIModel), not the provider
        model.provider = OpenAIProvider
        model.provider.complete.side_effect = lambda *args, **kwargs: dotable({
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": dotable(kwargs)
                    }
                }
            ]
        })
        # check mocked provider responses
        # using direct input
        # -- message is in system template
        result = model.complete('{context}')
        self.assertEqual(subdict(result.get('content').messages[0], ['role', 'content']),
                         {'role': 'system', 'content': 'system documents: the quick brown fox jumps over the lazy dog'})
        # -- message in prompt template
        result = model.complete('user documents: {context}')
        self.assertEqual(subdict(result.get('content').messages[1], ['role', 'content']),
                         {'role': 'user', 'content': 'user documents: the quick brown fox jumps over the lazy dog'})
        # check
        # using raw input
        # -- message is in system template
        result = model.complete([
            {'role': 'user',
             'content': ''}
        ])
        self.assertEqual(subdict(result.get('content').messages[0], ['role', 'content']),
                         {'role': 'system', 'content': 'system documents: the quick brown fox jumps over the lazy dog'})
        # -- message in prompt template
        result = model.complete([
            {'role': 'user',
             'content': 'user documents: {context}'}
        ])
        self.assertEqual(subdict(result.get('content').messages[1], ['role', 'content']),
                         {'role': 'user', 'content': 'user documents: the quick brown fox jumps over the lazy dog'})
