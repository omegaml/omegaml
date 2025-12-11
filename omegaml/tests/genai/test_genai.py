import inspect
import warnings
from types import FunctionType
from unittest import TestCase, mock
from unittest.mock import patch

from omegaml.backends.genai import SimpleEmbeddingModel
from omegaml.backends.genai.models import GenAIBaseBackend, GenAIModel, virtual_genai, GenAIModelHandler
from omegaml.backends.genai.textmodel import TextModelBackend, TextModel
from omegaml.backends.virtualobj import virtualobj
from omegaml.client.util import AttrDict, dotable, subdict
from omegaml.tests.util import OmegaTestMixin


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
        self.om.models.register_backend(TextModelBackend.KIND, TextModelBackend)

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

    def test_prompts_base_model(self):
        om = self.om

        # test save and restore
        class MyModel(GenAIModelHandler):
            def complete(self, prompt, messages=None, conversation_id=None,
                         data=None, **kwargs):
                return prompt

        om.models.put(MyModel, 'llms/mymodel')
        om.models.put('omegaml://models;model=llms/mymodel', 'prompts/myprompt')
        model = om.models.get('prompts/myprompt')
        self.assertIsInstance(model, GenAIModelHandler)

    def test_openai_put_get_default(self):
        # test save and restore
        meta = self.om.models.put('openai+https://localhost/mymodel', 'mymodel')
        self.assertEqual(meta.kind, TextModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'https://localhost:443')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')
        model = self.om.models.get('mymodel')
        self.assertIsInstance(model, TextModel)
        # default to http
        meta = self.om.models.put('openai+http://localhost;model=mymodel', 'mymodel', replace=True)
        self.assertEqual(meta.kind, TextModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'http://localhost:80')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')
        # replace
        meta = self.om.models.put('openai+https://localhost/v1;model=mymodel', 'mymodel', replace=True)
        self.assertEqual(meta.kind, TextModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'https://localhost:443/v1')
        self.assertEqual(meta.kind_meta['model'], 'mymodel')

    def test_placeholders_put_get(self):
        # test save and restore with secrets
        meta = self.om.models.put('openai+https://{OMEGA_LLM_APIKEY}@localhost/mymodel', 'mymodel')
        self.assertEqual(meta.kind, TextModelBackend.KIND)
        self.assertEqual(meta.kind_meta['base_url'], 'https://localhost:443')
        self.assertEqual(meta.kind_meta['creds'], '{OMEGA_LLM_APIKEY}')
        model = self.om.models.get('mymodel', secrets=dict(OMEGA_LLM_APIKEY='foobar'))
        self.assertEqual(model.api_key, 'foobar')
        self.assertIsInstance(model, TextModel)
        # test save and restore with omega defaults
        with patch.object(self.om.defaults, 'OMEGA_USERID', 'testuser', create=True):
            meta = self.om.models.put('openai+https://{OMEGA_USERID}@localhost/mymodel', 'mymodel')
            self.assertEqual(meta.kind, TextModelBackend.KIND)
            self.assertEqual(meta.kind_meta['base_url'], 'https://localhost:443')
            self.assertEqual(meta.kind_meta['creds'], '{OMEGA_USERID}')
            model = self.om.models.get('mymodel')
            self.assertEqual(model.api_key, 'testuser')
            self.assertIsInstance(model, TextModel)

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
    def test_openai_completion(self, OpenAIProvider):
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
        model_name = kwargs['model']
        self.assertEqual(model_name, 'mymodel')
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
    def test_openai_chat(self, OpenAIProvider):
        meta = self.om.models.put('openai+http://localhost/mymodel', 'mymodel')
        model = self.om.models.get('mymodel', data_store=self.om.datasets)
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
        conversation_id, result = model.chat('hello')
        model.provider = OpenAIProvider
        model.provider.complete.assert_called()
        kwargs = model.provider.complete.call_args.kwargs
        self.assertIn('model', kwargs)
        self.assertIn('messages', kwargs)
        model_name = kwargs['model']
        self.assertEqual(model_name, 'mymodel')
        self.assertEqual(model_name, 'mymodel')
        messages = kwargs['messages']
        # check all conversation ids are the same
        for message in messages:
            if conversation_id is not None:
                self.assertEqual(message['conversation_id'], conversation_id)
            else:
                conversation_id = message['conversation_id']
        # check conversation is returned as expected
        self.assertEqual(result['role'], 'assistant')
        self.assertEqual(result['content'], 'hello how are you')
        self.assertEqual(result['conversation_id'], conversation_id)
        # check we have a tracking log
        self.assertIsNotNone(model.tracking)
        conversation_log = model.conversation(raw=True)
        self.assertEqual(len(conversation_log), 3)  # system, user, assistant
        self.assertEqual(conversation_log[0]['role'], 'system')
        self.assertEqual(conversation_log[1]['role'], 'user')
        self.assertEqual(conversation_log[2]['role'], 'assistant')

    @mock.patch('omegaml.backends.genai.textmodel.OpenAIProvider')
    def test_openai_stream(self, OpenAIProvider):
        meta = self.om.models.put('openai+http://localhost/mymodel', 'mymodel')
        model = self.om.models.get('mymodel')
        # mock openai call
        # -- simulate tokenized responses, one character at a time
        assistant_response = 'hello how are you'
        openai_responses = [AttrDict({
            'choices': [AttrDict({
                'finish_reason': 'stop' if i == len(assistant_response) - 1 else None,
                'delta': AttrDict({
                    'role': 'assistant',
                    'content': c,
                })})]
        }) for i, c in enumerate(assistant_response)]
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
    def test_openai_stream_erronous(self, OpenAIProvider):
        meta = self.om.models.put('openai+http://localhost/mymodel', 'mymodel')
        model = self.om.models.get('mymodel')
        # mock openai call
        # -- simulate tokenized responses, one character at a time
        assistant_response = 'hello how are you'
        openai_responses = [AttrDict({
            'choices': [AttrDict({
                'finish_reason': 'stop' if i == len(assistant_response) - 1 else None,
                'delta': []  # invalid delta object (wrong type, should be {'content': ...} )
            })]
        }) for i, c in enumerate(assistant_response)]
        model.provider = OpenAIProvider
        model.provider.complete.return_value = openai_responses
        # check call raises errors
        with self.assertLogs(logger='omegaml') as log:
            warnings.simplefilter('always')
            result = list(model.complete('hello', stream=True))
            self.assertIn('could not process', ' '.join(log.output))
        # check stream completes ok
        self.assertEqual(result[-1].get('finish_reason'), 'stop.consolidated')

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
        result = model.embed('the quick brown fox jumps', raw=True)
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
    def test_tool_use_notrack(self, OpenAIProvider):
        # use tools/ prefix in attribute['tools']
        self._test_tool_use(OpenAIProvider, tracking=False, prefix='tools/')
        # don't use a prefix in attribute['tools']
        self._test_tool_use(OpenAIProvider, tracking=False, prefix='')

    @mock.patch('omegaml.backends.genai.textmodel.OpenAIProvider')
    def test_tool_use_tracked(self, OpenAIProvider):
        model = self._test_tool_use(OpenAIProvider, tracking=True)
        # check model tracking
        self.assertIsNotNone(model.tracking)
        data = model.tracking.data(event='toolcall')
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 2)  # not streamed, streamed

    def _test_tool_use(self, OpenAIProvider, tracking=False, prefix='tools/'):
        om = self.om

        # define a tool
        def weather():
            return 'sunny'

        om.models.put(weather, f'tools/weather')
        # check model definition includes tools
        meta = om.models.put('openai+http://localhost/mymodel', 'mymodel',
                             tools=[f'{prefix}weather'])
        self.assertEqual(meta.attributes['tools'], [f'{prefix}weather'])
        # check model triggers tools
        if not tracking:
            model = om.models.get('mymodel')
        else:
            model = om.models.get('mymodel', data_store=om.datasets)
        # mock openai call
        # -- Ref: https://platform.openai.com/docs/api-reference/chat/get
        # -- the model's response to initial prompt (calling a tool)
        openai_response_to_call_tool = dotable({
            "choices": [
                {
                    "finish_reason": "tool_calls",
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
                    "finish_reason": "tool_calls",
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
                    "finish_reason": "tool_calls",
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
        return model

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
                             documents='documents', template='user documents: {{ documents}} prompt: {{ prompt }}')
        model = om.models.get('mymodel', data_store=om.datasets)
        # mock model provider response
        # -- we test our TextModel(GenAIModel), not the provider
        model.provider = OpenAIProvider
        model.provider.complete.side_effect = lambda *args, **kwargs: dotable({
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": dotable(kwargs)
                    }
                }
            ]
        })
        # check mocked provider responses
        result = model.complete('hello')
        self.assertEqual(subdict(result.get('content').messages[1], ['role', 'content']),
                         {'role': 'user',
                          'content': 'user documents: the quick brown fox jumps over the lazy dog prompt: hello'})
        # using a single message as input
        # -- message is in system template
        result = model.complete({'role': 'user',
                                 'content': 'hello'})
        self.assertEqual(subdict(result.get('content').messages[1], ['role', 'content']),
                         {'role': 'user',
                          'content': 'user documents: the quick brown fox jumps over the lazy dog prompt: hello'})
        # using messages raw input
        # -- message is in system template
        result = model.complete([
            {'role': 'user',
             'content': 'hello'}
        ])
        self.assertEqual(subdict(result.get('content').messages[1], ['role', 'content']),
                         {'role': 'user',
                          'content': 'user documents: the quick brown fox jumps over the lazy dog prompt: hello'})

    @mock.patch('omegaml.backends.genai.textmodel.OpenAIProvider')
    def test_system_prompt(self, OpenAIProvider):
        om = self.om
        meta = self.om.models.put('openai+http://localhost/mymodel', 'mymodel', prompt='you are a test assistant')
        self.assertEqual(meta.attributes.get('prompt'), 'you are a test assistant')
        model = self.om.models.get('mymodel')
        self.assertEqual(model.prompt, 'you are a test assistant')
        model.provider = OpenAIProvider
        model.provider.complete.side_effect = lambda *args, **kwargs: dotable({
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": 'hello',
                    }
                }
            ]
        })
        model.complete('hello')
        model.provider.complete.assert_called()
        messages = model.provider.complete.call_args.kwargs.get('messages')
        self.assertEqual(messages[0]['role'], 'system')
        self.assertEqual(messages[0]['content'], 'you are a test assistant')

    @mock.patch('omegaml.backends.genai.textmodel.OpenAIProvider')
    def test_system_complete_strategy(self, OpenAIProvider):
        # test completion strategy is passed to provider as kwargs
        om = self.om
        meta = self.om.models.put('openai+http://localhost/mymodel', 'mymodel', strategy={
            'complete': {
                'extra_body': {
                    'reasoning': False,
                }
            }
        })
        self.assertEqual(meta.attributes.get('strategy'), {
            'complete': {
                'extra_body': {
                    'reasoning': False,
                }
            }
        })
        model = self.om.models.get('mymodel')
        self.assertIn('extra_body', model.strategy['complete'])
        model.provider = OpenAIProvider
        model.provider.complete.side_effect = lambda *args, **kwargs: dotable({
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": 'hello',
                    }
                }
            ]
        })
        model.complete('hello')
        model.provider.complete.assert_called()
        provider_kwargs = model.provider.complete.call_args.kwargs
        self.assertIn('extra_body', provider_kwargs)

    @mock.patch('omegaml.backends.genai.textmodel.OpenAIProvider')
    def test_system_template_render(self, OpenAIProvider):
        # test completion strategy is passed to provider as kwargs
        om = self.om
        template = "Today is {{ datetime }}. {{ prompt }}"
        meta = self.om.models.put('openai+http://localhost/mymodel', 'mymodel', template=template)
        self.assertEqual(meta.attributes.get('template'), template)
        model = self.om.models.get('mymodel')
        self.assertEqual(model.template, template)
        model.provider = OpenAIProvider
        model.provider.complete.side_effect = lambda *args, **kwargs: dotable({
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": 'hello',
                    }
                }
            ]
        })
        model.complete('hello')
        model.provider.complete.assert_called()
        messages = model.provider.complete.call_args.kwargs.get('messages')
        self.assertIn('Today is', messages[-1].get('content'))

    @mock.patch('omegaml.backends.genai.textmodel.OpenAIProvider')
    def test_messages_raw(self, OpenAIProvider):
        # test prompts/messages passed in from chat client handled correctly
        om = self.om
        om.models.put('openai+http://localhost/mymodel', 'mymodel')
        model = om.models.get('mymodel')
        model.provider = OpenAIProvider
        model.provider.complete.side_effect = lambda *args, **kwargs: dotable({
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": 'hello',
                    }
                }
            ]
        })
        messages = [{
            "role": "user",
            "content": "test"
        }]
        model.complete('', messages=messages, raw=True)
        model.provider.complete.assert_called()
        provider_messages = model.provider.complete.call_args.kwargs.get('messages')
        self.assertIsInstance(provider_messages, list)
        self.assertEqual(len(provider_messages), 2)
        self.assertEqual(provider_messages[0]['role'], 'system')
        self.assertEqual(provider_messages[1]['role'], 'user')

    def test_metadata_update(self):
        """ test metadata updates to strategy, systemprompt and tools work
        """
        om = self.om
        # try non-existing tool
        om.models.put('openai+http://localhost/mymodel', 'mymodel', tools=['xweather'])
        meta = om.models.metadata('mymodel')
        self.assertEqual(meta.attributes['tools'], ['xweather'])
        with self.assertRaises(ValueError) as cm:
            om.models.get('mymodel')
            self.assertIn('not a callable', cm.exception.args[0])

        # try existing tool
        # -- define a tool
        def weather():
            return 'sunny'

        om.models.put(weather, f'tools/weather')
        om.models.put('openai+http://localhost/mymodel', 'mymodel', tools=['weather'])
        meta = om.models.metadata('mymodel')
        self.assertEqual(meta.attributes['tools'], ['weather'])
        model = om.models.get('mymodel')
        self.assertTrue(callable(model.tools[0]))
        self.assertTrue(model.tools[0].__name__ == 'weather')
        # -- create model without tools
        om.models.put(weather, f'tools/weather')
        om.models.put('openai+http://localhost/mymodel', 'mymodel')
        # -- modify tools in metadata
        meta = om.models.metadata('mymodel')
        meta.attributes['tools'] = ['weather']
        meta.save(version=True)
        meta = om.models.metadata('mymodel')
        self.assertEqual(meta.attributes['tools'], ['weather'])
        # -- check tool works
        model = om.models.get('mymodel')
        self.assertTrue(callable(model.tools[0]))
        self.assertTrue(model.tools[0].__name__ == 'weather')

    @mock.patch('omegaml.backends.genai.textmodel.OpenAIProvider')
    def test_pipeline_basic_steps(self, OpenAIProvider):
        om = self.om

        @virtualobj
        def pipeline(method=None, **kwargs):
            import omegaml as om
            with om.runtime.experiment('test') as exp:
                exp.log_event('pipeline', method, kwargs)
            if method == 'prepare':
                prompt = kwargs.get('prompt_message')
                prompt['content'] = '**modified message**'
                return kwargs.get('messages')
            if method == 'process':
                response = kwargs['response_message']
                response['content'] += ' **modified response**'
                return response

        om.models.put(pipeline, 'pipeline')
        om.models.put('openai+http://localhost/mymodel', 'mymodel', pipeline='pipeline')
        model = om.models.get('mymodel')
        model.provider = OpenAIProvider
        model.provider.complete.side_effect = lambda *args, **kwargs: dotable({
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": 'hello ' + kwargs['messages'][-1]['content'],
                    }
                }
            ]
        })
        # call completion
        result = model.complete('hello')
        # check input and outputs have actually been processed by the pipeline
        # -- all pipeline steps are logged
        exp = om.runtime.experiment('test')
        steps = exp.data(event='pipeline')['key'].unique()
        self.assertEqual(set(steps), {'template', 'prepare', 'complete', 'process'})
        # -- result reflects input (prepare)
        self.assertIn('**modified message**', result['content'])
        # -- pipeline reflects output (process)
        self.assertIn('**modified response**', result['content'])
