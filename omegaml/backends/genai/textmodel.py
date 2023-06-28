from collections import namedtuple

import json
import re
import requests
from omegaml.backends.genai.index import DocumentIndex
from omegaml.backends.genai.models import GenAIBaseBackend, GenAIModel
from omegaml.store import OmegaStore
from omegaml.util import ensure_list, tryOr
from openai import OpenAI
from urllib.parse import urlparse, parse_qs, urljoin
from uuid import uuid4


class TextModelBackend(GenAIBaseBackend):
    """ Backend for OpenAI models

    Enables creating an OpenAI model via a connection string, e.g.
    om.models.put('openai://<base_url>;model=<model>', 'mymodel'). The connection
    string must be in the format openai://<base_url>;model=<model> where <base_url>
    is the base URL of the OpenAI-compatible model server's REST API, and <model>
    is the model name as known to the model server. The connection string may also
    include an apikey, e.g. 'openai://<apikey>@<base_url>;model=<model>'.

    Usage:
        # create a model
        om.models.put('openai://localhost:8000/mymodel', 'mymodel')
        # get the model
        model = om.models.get('mymodel')
        # use the model
        result = model.complete('hello, how are you?')

    Notes:
        * the actual implementation of the model handling logic is in OpenAIModel,
          this only provides the model store interface and acts as any VirtualObjectHandler
    """
    KIND = 'genai.text'

    @classmethod
    def supports(cls, obj, name, **kwargs):
        return isinstance(obj, str) and re.match(r'openai(\+.*)?://', obj)

    def _parse_url(self, obj):
        # properly parse RFC 1808 URLs
        # -- format: <vendor>+<protocol>://<base_url>;<params>?<query>
        # -- https://datatracker.ietf.org/doc/html/rfc1808#section-2.1
        # Python urlparse does not support ;params parsing in custom schemes
        # -- depending on the path, ;params ends up in path, netloc or hostname
        # -- we fix that by adjusting the parsed result
        # -- .vendor is the vendor, e.g. openai
        # -- .scheme is the protocol, e.g. https
        parsed = urlparse(obj)
        vendor, scheme = parsed.scheme.split('+') if '+' in parsed.scheme else ('', 'https')
        path, params = parsed.path.split(';', 1) if ';' in parsed.path else (parsed.path, '')
        netloc, params = parsed.netloc.split(';', 1) if ';' in parsed.netloc else (parsed.netloc, params)
        hostname, params = parsed.hostname.split(';', 1) if ';' in parsed.hostname else (parsed.hostname, params)
        port = parsed.port or (443 if scheme == 'https' else 80)
        ParseResult = namedtuple('ParseResult', ['vendor', 'scheme',
                                                 'path', 'params', 'netloc', 'hostname', 'port', 'username', 'password',
                                                 'query'])
        return ParseResult(vendor, scheme, path, params, netloc, hostname, port, parsed.username,
                           parsed.password, parsed.query)

    def put(self, obj, name, template=None, pipeline=None, provider=None, tools=None, documents=None, **kwargs):
        self.model_store: OmegaStore
        parsed = self._parse_url(obj)
        params = parse_qs(parsed.params)
        if 'model' in params:
            model = params.pop('model')[0]
            path = parsed.path
        else:
            path, model = parsed.path.split('/', 1) if '/' in parsed.path else (parsed.path, None)
        assert model, f'no model specified in {obj}, use openai://<base_url>;model=<model> or openai+<scheme>://<base_url>;model=<model>'
        base_url = f'{parsed.scheme}://{parsed.hostname}:{parsed.port}{path}'
        creds = f'{parsed.username}:{parsed.password}' if parsed.username and parsed.password else ''
        creds = creds or f'{parsed.username}' if parsed.username else ''
        query = parse_qs(parsed.query)
        params = params or {}
        query = query or {}
        provider = provider or self._infer_provider(base_url)
        kind_meta = {
            'base_url': base_url,
            'creds': creds,
            'model': model,
            'query': query,
            'params': params,
            'provider': provider,
        }
        attributes = {
            'template': template or query.get('template'),
            'dataset': self._messages_dataset(name),
            'pipeline': pipeline or None,
            'tools': tools or [],
            'documents': documents or [],
        }
        kwargs.update(attributes=attributes)
        meta = self.model_store.make_metadata(name,
                                              kind=self.KIND,
                                              kind_meta=kind_meta,
                                              **kwargs)
        return meta.save()

    def get(self, name, template=None, data_store=None, pipeline=None, tools=None, documents=None, **kwargs):
        meta = self.model_store.metadata(name)
        kind_meta = meta.kind_meta
        base_url = kind_meta['base_url']
        model = kind_meta['model']
        query = kind_meta['query']
        params = kind_meta['params']
        creds = kind_meta['creds']
        provider = kind_meta['provider']
        pipeline = pipeline or meta.attributes.get('pipeline')
        tools = tools or meta.attributes.get('tools') or []
        documents = documents or meta.attributes.get('documents')
        params.update(kwargs)
        template = template or query.get('template') or meta.attributes.get('template')
        data_store = data_store or (self.data_store if self.data_store is not self.model_store else None)
        # load dependencies
        pipeline = self._load_pipeline(pipeline)
        documents = self._load_documents(documents)
        tools = self._load_tools(tools)
        # build actual model instance
        model = TextModel(base_url, model, api_key=creds, template=template,
                          data_store=data_store, pipeline=pipeline, tools=tools,
                          dataset=self._messages_dataset(name, meta=meta),
                          provider=provider, documents=documents,
                          **params)
        return model

    def drop(self, name, data_store=None, force=False, **kwargs):
        meta = self.model_store.metadata(name)
        data_store = data_store or (self.data_store if self.data_store is not self.model_store else None)
        if data_store:
            self.data_store.drop(self._messages_dataset(name, meta=meta), force=force, **kwargs)
        return self.model_store._drop(name, force=force, **kwargs)

    def _messages_dataset(self, name, meta=None, user=None):
        user = user or self.model_store.defaults.get('OMEGA_USERID', 'default')
        return f'./openai/messages/{name}' if meta is None else meta.attributes.get('dataset').format(name=name,
                                                                                                      user=user)

    def _load_tools(self, tools):
        tool_fns = [tool if callable(tool) else self.model_store.get(f'tools/{tool}') for tool in tools]
        return tool_fns

    def _load_documents(self, documents):
        documents = self.data_store.get(documents, model_store=self.model_store) if isinstance(documents,
                                                                                               str) else documents
        return documents

    def _load_pipeline(self, pipeline):
        pipeline = pipeline if callable(pipeline) else (
            self.model_store.get(pipeline) if isinstance(pipeline, str) else None)
        return pipeline

    def _infer_provider(self, url):
        for provider, cls in PROVIDERS.items():
            if cls.match_url(url):
                return provider
        return 'default'


class TextModel(GenAIModel):
    """ OpenAI model

    This implements the OpenAI model interface. It is a thin wrapper around the OpenAI API,
    and adds conversation tracking and data storage for the conversation history. For chat completions,
    the conversation history is stored in a dataset named ./openai/messages/<modelname>/<user>. For
    completions without a conversation id, a new conversation id is generated and returned in each
    message, however the conversation history is not stored in this case. The complete() method
    can be called with a conversation id to continue a conversation, in this case it is equivalent
    to chat().

    The model implements a callback to a user function or virtul object handler, called the pipeline.
    The pipeline is called with the method name, the conversation id, the prompt message, and
    the messages so far. It can be used to implement custom logic for preparing the messages and
    the response.

    Usage:

        Create and access a model::

            # create a model
            om.models.put('openai://localhost:8000/mymodel', 'mymodel')
            model = om.models.get('mymodel')
            # complete a prompt
            result = model.complete('hello, how are you?')
            # chat
            conversation_id, result = model.chat('hello, how are you?')
            # continue a conversation
            result = model.complete('I am fine, thank you.', conversation_id=conversation_id)

        Implement a pipeline::

            # add a pipeline
            @virtual_genai
            def my_pipeline(method, conversation_id, prompt_message, messages):
                # implement your logic here
                if method == 'prepare':
                    # prepare the initial messages
                    return messages
                elif method == 'template':
                    # prepare the template
                    return 'You are a helpful assistant.'
                elif method == 'process':
                    # process the response
                    return response_message

            model = om.models.get('mymodel', pipeline=my_pipeline)
            result = model.complete('hello, how are you?')

            # store the pipeline in a virtual object
            om.models.put(my_pipeline, 'my_pipeline')
            model = om.models.put('openai://localhost:8000/mymodel', 'mymodel', pipeline='my_pipeline')
            # this will automatically load the pipeline, and get it called for each stage
            result = model.complete('hello, how are you?')

        A pipeline can be used to implement custom logic for preparing the messages and to check
        or change the response. The pipeline can return any messages, a custom template, or
        a custom response.

        Get back the conversation history::

            model = om.models.get('mymodel')
            messages = model.conversation(conversation_id)
    """

    def __init__(self, base_url, model, api_key=None, template=None, data_store=None,
                 dataset=None, pipeline=None, provider='openai', tools=None, documents=None, **kwargs):
        super().__init__()
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.kwargs = kwargs
        self.template = template or 'You are a helpful assistant.'
        self.data_store = data_store
        self.dataset = dataset
        self.provider = PROVIDERS[provider](
            api_key=api_key,
            base_url=base_url,
            model=model)
        self.pipeline = pipeline or (lambda *args, **kwargs: None)
        self.tools = tools
        self.tools_specs = [self._get_function_spec(tool) for tool in tools] if tools else None
        self.documents = documents

    def load(self, method):
        pass

    def embed(self, documents, dimensions=None, **kwargs):
        dimensions = dimensions or self.kwargs.get('dimensions', 256)
        embeddings = self.provider.embed(documents, dimensions=dimensions, model=self.model,
                                         **kwargs)
        return embeddings

    def complete(self, prompt, messages=None, conversation_id=None, raw=False, data=None,
                 chat=False, stream=False, use_tools=True, **kwargs):

        def parse_completion_response(r):
            response, _, response_message = r
            return response_message

        def parse_chat_response(r):
            conversation_id, response, _, response_message = r
            return response_message

        if not chat and conversation_id is None:
            responses = self._do_complete(prompt, messages=messages, data=data,
                                          stream=stream, use_tools=use_tools, raw=raw, **kwargs)
            response_parser = parse_completion_response
        else:
            # chat or conversation id provided
            responses = self._do_chat(prompt, conversation_id=conversation_id,
                                      data=data,
                                      stream=stream,
                                      use_tools=use_tools,
                                      raw=raw,
                                      **kwargs)
            response_parser = parse_chat_response
        # return response(s)
        response_gen = (response_parser(response) for response in responses)
        return response_gen if stream else [response for response in response_gen][-1]

    def chat(self, prompt, conversation_id=None, raw=False, stream=False, use_tools=True, **kwargs):
        responses = self._do_chat(prompt,
                                  conversation_id=conversation_id,
                                  stream=stream,
                                  use_tools=use_tools,
                                  **kwargs)

        def response_parser(r):
            conversation_id, response, prompt_response, response_message = r
            return conversation_id, (response if raw else response_message)

        response_gen = (response_parser(response) for response in responses)
        return response_gen if stream else [response for response in response_gen][-1]

    def _do_chat(self, prompt, conversation_id=None, data=None, use_tools=False, raw=False, **kwargs):
        assert self.data_store, "chat requires a data_store, specify data_store=om.datasets"
        conversation_id = conversation_id or uuid4().hex
        messages = self.conversation(conversation_id)
        if hasattr(messages, 'to_dict'):
            # convert pandas dataframe to records
            messages = messages.to_dict('records')
        if messages is None:
            messages = [self._system_message(prompt, conversation_id=conversation_id)]
            self.data_store.put(messages, self.dataset, kind='pandas.rawdict')
        responses = self._do_complete(prompt, messages, conversation_id=conversation_id, data=data,
                                      use_tools=use_tools, raw=raw, **kwargs)
        to_store = []
        for response in responses:
            response, prompt_message, response_message = response
            # wrapping in dict() to avoid modification by the data store (e.g. adding _id)
            to_store = [
                dict(prompt_message),
                dict(response_message)
            ]
            yield conversation_id, response, prompt_message, response_message
        else:
            self.data_store.put(to_store, self.dataset, kind='pandas.rawdict')

    def _call_tools(self, tool_calls, conversation_id):
        # process tool calls
        results = []
        tool_prompts = []
        for tool_call in tool_calls:
            tool = [(ts, tf) for ts, tf in zip(self.tools_specs, self.tools)
                    if tf.__name__ == tool_call['function']['name']]
            if tool:
                tool, tool_func = tool[0]
                tool_kwargs = json.loads(tool_call['function']['arguments'])
                try:
                    tool_result = tool_func(**tool_kwargs)
                except Exception as e:
                    tool_result = str(e)
                tool_response = {
                    "role": "assistant",
                    "content": tool_result,
                    "conversation_id": conversation_id,
                }
                results.append(tool_response)
                tool_prompts.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": str(tool_result)
                })
        return results, tool_prompts

    def conversation(self, conversation_id=None, raw=False):
        if conversation_id is None:
            filter = {}
        else:
            filter = {'conversation_id': conversation_id}
        messages = self.data_store.get(self.dataset, **filter)
        if messages is not None:
            messages = messages[[c for c in messages.columns if c != '_id']]
        return messages if not raw else messages.to_dict('records')

    def _system_message(self, prompt, conversation_id=None):
        return {
            "role": "system",
            "content": self._augment_prompt(self.template, self.documents, query=prompt),
            "conversation_id": conversation_id or uuid4().hex,
        }

    def _do_complete(self, prompt, messages=None, conversation_id=None, data=None, stream=False,
                     use_tools=False, raw=False, **kwargs):
        conversation_id = conversation_id or uuid4().hex
        messages = messages or []
        if prompt and isinstance(prompt, str):
            # support direct text input
            prompt_message = {
                "role": "user",
                "content": self._augment_prompt(prompt, self.documents),
                "conversation_id": conversation_id,
            }
            messages = ([self._system_message(prompt, conversation_id=conversation_id)] +
                        [self._augment_message(m, self.documents) for m in messages])
        elif isinstance(prompt, dict):
            # support structured input
            # -- see OpenAI /chat/completions endpoint, "messages" parameter
            #    https://platform.openai.com/docs/api-reference/chat
            # -- assume prompt is a fully formed provider-compatible message,e.g. from a chat client
            messages = ([self._system_message(prompt.get('content', ''), conversation_id=conversation_id)] +
                        [self._augment_message(m, self.documents) for m in messages])
            prompt_message = prompt
        elif isinstance(prompt, list):
            # support structured input, as messages
            # -- see OpenAI /chat/completions endpoint, "messages" parameter
            #    https://platform.openai.com/docs/api-reference/chat
            # -- assume prompt is a fully formed provider-compatible message,e.g. from a chat client
            prompts = '\n\n'.join(m.get('content', '') for m in prompt)
            messages = ([self._system_message(prompts,
                                              conversation_id=conversation_id)] +
                        [self._augment_message(m, self.documents) for m in prompt])
            prompt_message = None
        else:
            # raw input, assume messages contains the user prompt
            prompt_message = None
            prompts = '\n\n'.join(m.get('content', '') for m in messages)
            messages = ([self._system_message(prompts,
                                              conversation_id=conversation_id)] +
                        [self._augment_message(m, self.documents) for m in messages])
        if self.tools:
            kwargs.update(tools=self.tools_specs,
                          tool_choice='auto')
        _template = self._prepare_template(self.template,
                                           data=data)
        template = self.pipeline(method='template',
                                 prompt_message=prompt_message,
                                 messages=messages,
                                 template=self.template,
                                 conversation_id=conversation_id,
                                 **kwargs) or _template
        _default_messages = (messages + [prompt_message]) if prompt_message else messages
        messages = self.pipeline(method='prepare',
                                 prompt_message=prompt_message,
                                 messages=messages,
                                 template=template,
                                 conversation_id=conversation_id, **kwargs) or _default_messages
        response = self.provider.complete(
            messages=messages,
            stream=stream,
            model=self.model,
            **kwargs
        )

        def maybe_call_tools(response, prompt_message, response_message, use_tools=False, as_delta=False):
            """ prepare calling tools, optionally actually call the selected tool """
            if hasattr(response.choices[0], 'delta'):
                message = response.choices[0].delta
            else:
                message = response.choices[0].message
            if self.tools and getattr(message, 'tool_calls', None):
                # call tools
                response_message['tool_calls'] = message.to_dict()['tool_calls']
                tool_calls = [tool.to_dict() for tool in message.tool_calls]
            else:
                tool_calls = None
            if use_tools and tool_calls:
                results, tool_prompts = self._call_tools(tool_calls, conversation_id)
                # ask llm to respond to tool results
                # -- avoid recursive tool calls
                # -- never stream results
                kkwargs = dict(kwargs)
                kkwargs.pop('stream', None)
                kkwargs.pop('tools', None)
                kkwargs.pop('tool_choice', None)
                toolcall_messages = messages + [prompt_message] + [message] + tool_prompts
                toolcall_messages = self.pipeline(method='toolcall',
                                                  prompt_message=prompt_message,
                                                  messages=toolcall_messages,
                                                  template=template,
                                                  conversation_id=conversation_id, **kwargs) or toolcall_messages
                response = self.provider.complete(
                    messages=toolcall_messages,
                    model=self.model,
                    **kkwargs,
                )
                tooled_response, tooled_prompt_message, tooled_response_message = resolve_response(response,
                                                                                                   prompt_message,
                                                                                                   use_tools=False)
                tooled_response_message['intermediate_results'] = {
                    'tool_calls': tool_calls,
                    'tool_prompts': tool_prompts,
                    'tool_results': results,
                }
                tooled_response_message = self.pipeline(method='toolresult', response_message=tooled_response_message,
                                                        prompt_message=prompt_message,
                                                        messages=toolcall_messages,
                                                        template=template,
                                                        conversation_id=conversation_id,
                                                        **kwargs) or tooled_response_message
                if as_delta:
                    # ensure the tool response is shown as a delta chunk
                    if raw:
                        tooled_response_message['choices'][0]['delta'] = tooled_response_message['choices'][0].pop(
                            'message', None)
                    else:
                        tooled_response_message['delta'] = response_message['content']
                return tooled_response, prompt_message, tooled_response_message
            return response, prompt_message, response_message

        def resolve_response(response, prompt_message, use_tools=False):
            if raw:
                # native response message
                # Ref: https://platform.openai.com/docs/api-reference/chat/get
                response_message = response.to_dict()
            elif getattr(response, 'error', None):
                return response, prompt_message, {
                    "role": "system",
                    "content": response.error.get('message', str(response.error)),
                    "conversation_id": conversation_id,
                    "error": response.error,
                }
            else:
                response_message = {
                    "role": response.choices[0].message.role,
                    "content": tryOr(lambda: response.choices[0].message.content, None),
                    "conversation_id": conversation_id,
                }
            response, prompt_message, response_message = maybe_call_tools(response, prompt_message,
                                                                          response_message, use_tools=use_tools)
            response_message = self.pipeline(method='process', response_message=response_message,
                                             prompt_message=prompt_message,
                                             messages=messages,
                                             template=template,
                                             conversation_id=conversation_id,
                                             **kwargs) or response_message
            return response, prompt_message, response_message

        def resolve_chunk(response, chunk, chunks, prompt_message, use_tools=False):
            if raw:
                response_message = chunk.to_dict()
            else:
                response_message = {
                    "role": chunk.choices[0].delta.role,
                    "delta": chunk.choices[0].delta.content,
                    "content": ''.join(c['delta'] for c in chunks) + str(chunk.choices[0].delta.content or ''),
                    "conversation_id": conversation_id,
                }
            response, prompt_message, response_message = maybe_call_tools(chunk, prompt_message,
                                                                          response_message, use_tools=use_tools,
                                                                          as_delta=True)
            chunks.append(response_message)
            response_message = self.pipeline(method='process', response_message=response_message,
                                             prompt_message=prompt_message,
                                             messages=messages,
                                             template=template,
                                             conversation_id=conversation_id,
                                             **kwargs) or response_message
            return response, prompt_message, response_message

        if stream:
            # https://cookbook.openai.com/examples/how_to_stream_completions
            print("*** streaming")
            chunks = []
            for chunk in response:
                yield resolve_chunk(response, chunk, chunks, prompt_message, use_tools=use_tools)
        else:
            yield resolve_response(response, prompt_message, use_tools=use_tools)

    def _parsed_completion(self, response):
        return response.choices[0].message.content

    def _prepare_template(self, template, data=None):
        _template = (template or '').format_map(safeformat(data or {}))
        return template

    def _get_function_spec(self, func):
        """
        Generates an OpenAI SDK function dictionary from an annotated function.

        Args:
            func (callable): The annotated function to be converted.

        Returns:
            dict: The OpenAI SDK function dictionary.

        References:
            - https://platform.openai.com/docs/api-reference/debugging-requests
        """
        if isinstance(func, dict):
            return func
        import inspect
        sig = inspect.signature(func)
        params = {}
        TYPES = {
            str: 'string',
            int: 'integer',
            float: 'float',
            list: 'list',
        }
        for param in sig.parameters.values():
            param_type = TYPES.get(
                param.annotation) or 'string' if param.annotation != inspect.Parameter.empty else None
            param_default = param.default if param.default != inspect.Parameter.empty else None
            param_type = param_type or TYPES.get(type(param_default))
            param_dict = {
                "name": param.name,
                "type": param_type,
                "description": f'represents {param.name}',
                "default": param_default,
            }
            params[param.name] = param_dict

        return_type = str(sig.return_annotation) if sig.return_annotation != inspect.Parameter.empty else None

        function_dict = {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": inspect.getdoc(func) or 'A function to return a response',
                "parameters": {
                    "type": "object",
                    "properties": {
                        k: v for k, v in params.items()
                    },
                },
                "return_type": return_type,
            }
        }

        return function_dict

    def _augment_prompt(self, prompt, documents: DocumentIndex, query=None):
        query = query or prompt
        if documents is None or '{context}' not in prompt:
            return prompt
        docs = documents.retrieve(query)
        if docs:
            context = ensure_list(docs)[0].get('text')
        else:
            context = '(error: no documents found)'
        return prompt.format_map(safeformat(context=context))

    def _augment_message(self, message, documents: DocumentIndex, query=None):
        augmented = self._augment_prompt(message.get('content', ''), documents=documents, query=query)
        message['content'] = augmented if augmented else message.get('content')
        return message


class Provider:
    URL_REGEX = None

    def __init__(self, api_key, base_url, model=None, **kwargs):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

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
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url)
        self.model = self.model

    def embed(self, documents, dimensions=None, model=None, **kwargs):
        documents = ensure_list(documents)
        embeddings = self.client.embeddings.create(
            model=model or self.model,
            input=documents,
            dimensions=dimensions,
            encoding_format="float"
        )
        return embeddings

    def complete(self, messages, stream=False, model=None, **kwargs):
        response = self.client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            stream=stream,
            **kwargs
        )
        return response


class JinaEmbeddingsProvider(Provider):
    URL_REGEX = r'https?://(api\.jina\.ai)(:\d+)?/.*'

    def embed(self, documents, dimensions=None, model=None, **kwargs):
        """ Embed documents using Jina AI's embedding service.

        Args:
            documents (list): List of documents to embed.
            dimensions (int): Number of dimensions to embed to.
            model (str): Model name to use for embedding.

        Returns:
            list: List of embeddings as list[list[float, ...]].
        """
        # see https://jina.ai/embeddings
        documents = ensure_list(documents)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        url = urljoin(self.base_url, 'embeddings')
        resp = requests.post(url,
                             headers=headers,
                             json={'model': self.model,
                                   'input': [{
                                       'text': doc
                                   } for doc in documents]})
        assert resp.status_code == 200, f'Error {resp.status_code} calling {url}: {resp.text}'
        data = resp.json().get('data', [])
        return [d['embedding'] for d in sorted(data, key=lambda x: x['index'])]


class AnythingLLMProvider(Provider):
    URL_REGEX = r'https?://(api\.anythingllm\.com|localhost:(3001)+|anythingllm\.com)/.*'

    def embed(self, documents, dimensions=None, **kwargs):
        """ Embed documents

        Args:
            documents (list): list of documents to embed
            dimensions (int): number of dimensions to embed to

        Returns:
            list: list of embeddings as list[list[float, ...]]
        """
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }
        url = urljoin(self.base_url, 'embeddings')
        documents = ensure_list(documents)
        resp = requests.post(url,
                             headers=headers,
                             json={'inputs': documents,
                                   'model': self.model})
        assert resp.status_code == 200, f'Error {resp.status_code} calling {url}: {resp.text}'
        data = resp.json().get('data', [])
        return [d['embedding'] for d in data]

    def complete(self, messages, stream=False, **kwargs):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }
        url = f'{self.base_url}/chat/completions'
        resp = requests.post(url,
                             headers=headers,
                             json={'messages': messages,
                                   'model': self.model,
                                   'stream': stream})
        return resp.json()


PROVIDERS = {
    'openai': OpenAIProvider,
    'anythingllm': AnythingLLMProvider,
    'jina': JinaEmbeddingsProvider,
    'default': OpenAIProvider,
}


class safeformat(dict):
    def __missing__(self, key):
        return f"{{{key}}}"  # return "{<key>}"
