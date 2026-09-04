import json
import logging
import os
import re
from collections import namedtuple
from getpass import getuser
from inspect import isclass
from itertools import chain
from pprint import pformat
from urllib.parse import parse_qs, urljoin, urlsplit
from uuid import uuid4

import pandas as pd
import requests
from jinja2.sandbox import SandboxedEnvironment
from openai import OpenAI

from omegaml.backends.genai.index import DocumentIndex
from omegaml.backends.genai.models import GenAIBaseBackend, GenAIModel
from omegaml.backends.guardrails import GuardrailPolicy
from omegaml.backends.tracking import NoTrackTracker, OmegaSimpleTracker
from omegaml.store import OmegaStore
from omegaml.util import KeepMissing, dict_merge, ensure_dict, ensure_list, raise_, utcnow

logger = logging.getLogger(__name__)


class TextModelBackend(GenAIBaseBackend):
    """Backend for OpenAI models

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
    STORED_MODEL_URL = 'omegaml://models'

    @classmethod
    def supports(cls, obj, name, **kwargs):
        return isinstance(obj, str) and (re.match(r'openai(\+.*)?://', obj) or obj.startswith(cls.STORED_MODEL_URL))

    def _parse_url(self, obj):
        # properly parse RFC 1808 URLs
        # -- format: <vendor>+<protocol>://<base_url>;<params>?<query>
        # -- https://datatracker.ietf.org/doc/html/rfc1808#section-2.1
        # Python urlparse does not support ;params parsing in custom schemes
        # -- depending on the path, ;params ends up in path, netloc or hostname
        # -- we fix that by adjusting the parsed result
        # -- .vendor is the vendor, e.g. openai
        # -- .scheme is the protocol, e.g. https
        uri, params = obj.split(';', 1) if ';' in obj else (obj, '')
        parsed = urlsplit(uri)
        vendor, scheme = parsed.scheme.split('+') if '+' in parsed.scheme else ('', parsed.scheme)
        path, params = parsed.path.split(';', 1) if ';' in parsed.path else (parsed.path, params)
        netloc, params = parsed.netloc.split(';', 1) if ';' in parsed.netloc else (parsed.netloc, params)
        hostname, params = parsed.hostname.split(';', 1) if ';' in parsed.hostname else (parsed.hostname, params)
        port = parsed.port or (443 if scheme == 'https' else 80)
        ParseResult = namedtuple(
            'ParseResult',
            ['vendor', 'scheme', 'path', 'params', 'netloc', 'hostname', 'port', 'username', 'password', 'query'],
        )
        return ParseResult(
            vendor, scheme, path, params, netloc, hostname, port, parsed.username, parsed.password, parsed.query
        )

    def put(
            self,
            obj,
            name,
            template=None,
            prompt=None,
            pipeline=None,
            provider=None,
            guardrails=None,
            tools=None,
            documents=None,
            strategy=None,
            apikey=None,
            **kwargs,
    ):
        """save a conversational LLM model served by an OpenAI-compatible /chat/completions or /embeddings endpoints

        Args:
            obj (str): the URL in the form 'openai+http(s)://<credentials>@<server:port>/api/v1;model=<modelname>'.
               The URL may use {PLACHOLDER} referencing om.defaults or env variables to resolve at runtime. The
               URL may also refer to another model previously stored by using the 'omegaml://models?model=<modelname>'
               format, overriding all of its specified parameters. Use this to store custom model configurations for the
               same base model.
            name (str): the name of the object in om.models
            template (str): optional, the Jinja template string to be applied to prompts
            prompt (str): optional, the system prompt, defaults to 'You are a helpful assisstant'
            pipeline (str): optional, the name of a @virtualobj function stored in om.models
            provider (str): optional, the client to access the <server:port> provider API, defaults to 'openai' (see
               omegaml.genai.textmodel.PROVIDERS)
            tools (list): optional, the list of tool names stored in om.models as 'tools/<name>'
            guardrails (list): optiona, the list of guardrail names stored in om.models as 'policy/<name>'
            documents (str): optional, the name of a document store stored in om.datasets
            strategy (dict): optional, kwargs to various parts of the pipeline ('retrieve', 'complete', 'agentic')
            apikey (str): optional, the api key to use, if <credentials> is not part of the URL
            **kwargs:

        Returns:
            metadata (Metadata): the TextModel's metadata object

        .. versionchanged:: NEXT
            strategy=dict(agentic=True) causes model.complete() to recursively resolve tool calls until no
            further tools are called by the model. See model.complete() for details
        """
        self.model_store: OmegaStore
        parsed = self._parse_url(obj)
        params = parse_qs(parsed.params)
        if 'model' in params:
            model = params.pop('model')[0]
            path = parsed.path
        else:
            path, model = parsed.path.split('/', 1) if '/' in parsed.path else (parsed.path, None)
        assert model, (
            f'no model specified in {obj}, use openai://<base_url>;model=<model> or openai+<scheme>://<base_url>;model=<model>'
        )
        base_url = f'{parsed.scheme}://{parsed.hostname}:{parsed.port}{path}'
        uri_creds = f'{parsed.username}:{parsed.password}' if parsed.username and parsed.password else ''
        uri_creds = uri_creds or f'{parsed.username}' if parsed.username else ''
        creds = apikey or uri_creds
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
            'prompt': prompt or query.get('prompt'),
            'template': template or query.get('template'),
            'pipeline': pipeline or None,
            'tools': ensure_list(tools or []),
            'guardrails': ensure_list(guardrails or []),
            'documents': documents or [],
            'strategy': strategy or {},
        }
        kwargs.update(attributes=attributes)
        meta = self.model_store.make_metadata(name, kind=self.KIND, kind_meta=kind_meta, **kwargs)
        return meta.save()

    def get(
            self,
            name,
            prompt=None,
            template=None,
            data_store=None,
            pipeline=None,
            tools=None,
            guardrails=None,
            documents=None,
            strategy=None,
            tracking=None,
            secrets=None,
            **kwargs,
    ):
        """get a TextModel

        Args:
            name (str): the name of the model, as stored using om.models.put()
            prompt (str): optional, the system prompt to use, defaults to metadata.attributes.prompt
            template (str): optional, the template to use for input prompts, defaults ot metadata.attributes.template
            data_store (OmegaStore): optional, the datastore to use for tracking and document stores
            pipeline (str): optional, the name of the @virtualobj pipeline stored in om.models, defaults to
               metadata.attributes.pipeline
            tools (list): optional, the list of tool names stored in om.models
            guardrails (list): optional, the list of policy names stored in om.models
            documents (str): optional, the list of document stores in om.datasets, if specified requires passing
               of data_store=, defaults to metadata.attributes.tools
            strategy (dict): optional, see .put()
            tracking (TrackingProvider): optional, a tracking provider
            secrets (dict): optional, used to resolve {PLACEHOLDERS} in the model's url
            **kwargs:

        Returns:
            model (TextModel): the instance of TextModel
        """
        meta = self.model_store.metadata(name)
        secrets = secrets or {}
        # setup from connection string
        kind_meta = meta.kind_meta
        base_url = kind_meta['base_url']
        model = kind_meta['model']
        query = kind_meta['query']
        params = kind_meta['params']
        creds = kind_meta['creds']
        provider = kind_meta['provider']
        params.update(kwargs)
        # setup from attributes
        model = meta.attributes.get('model') or model
        pipeline = pipeline or meta.attributes.get('pipeline')
        tools = ensure_list(tools or meta.attributes.get('tools') or [])
        guardrails = ensure_list(guardrails or meta.attributes.get('guardrails') or [])
        documents = documents or meta.attributes.get('documents')
        template = template or query.get('template') or meta.attributes.get('template')
        prompt = prompt or query.get('prompt') or meta.attributes.get('prompt')
        strategy = {**(meta.attributes.get('strategy') or {}), **(strategy or {})}
        # load dependencies
        data_store = data_store or (self.data_store if self.data_store is not self.model_store else None)
        pipeline = self._load_pipeline(pipeline)
        documents = self._load_documents(documents)
        tools = self._load_tools(tools, 'tools')
        guardrails = self._load_guardrails(guardrails, 'policy', instance=True)
        base_url = self._resolve_placeholders(base_url, secrets)
        creds = self._resolve_placeholders(creds, secrets)
        self.tracking = tracking or self.tracking or self._ensure_tracking(meta)
        # infer model provider
        if base_url.startswith(self.STORED_MODEL_URL) and self.model_store.exists(model):
            # model is a stored model, load it
            model = self.model_store.get(
                model,
                **{
                    **dict(
                        prompt=prompt,
                        template=template,
                        data_store=data_store,
                        pipeline=pipeline,
                        tools=tools,
                        guardrails=guardrails,
                        documents=documents,
                        strategy=strategy,
                        tracking=self.tracking,
                    ),
                    **params,
                },
            )

        else:
            model = TextModel(
                base_url,
                model,
                **{
                    **dict(
                        api_key=creds,
                        prompt=prompt,
                        template=template,
                        data_store=data_store,
                        pipeline=pipeline,
                        tools=tools,
                        guardrails=guardrails,
                        tracking=self.tracking,
                        provider=provider,
                        documents=documents,
                        strategy=strategy,
                    ),
                    **params,
                },
            )
        return model

    def drop(self, name, data_store=None, force=False, **kwargs):
        meta = self.model_store.metadata(name)
        data_store = data_store or (self.data_store if self.data_store is not self.model_store else None)
        return self.model_store._drop(name, force=force, **kwargs)

    def _load_tools(self, tools, kind, instance=False):
        # works with or without prefix
        barename = lambda v: '{kind}/{v}'.format(kind=kind, v=str(v).replace(f'{kind}/', ''))
        verify = lambda t, fn: callable(fn) or raise_(ValueError(f'{t} is not a callable, got {fn}'))
        tool_fns = (tool if callable(tool) else self.model_store.get(f'{barename(tool)}') for tool in tools)
        tool_fns = (fn for tool, fn in zip(tools, tool_fns) if verify(tool, fn))
        tool_fns = (fn(self) if isclass(fn) and instance else fn for fn in tool_fns)
        return list(tool_fns)

    def _load_guardrails(self, tools, kind, instance=False):
        # load guardrails from policy, and load scanners to any GuardrailPolicy instances
        rails_fns = self._load_tools(tools, kind, instance=instance)
        for rails in rails_fns:
            # autoload scanners
            if isinstance(rails, GuardrailPolicy) and not rails.scanners:
                path = f'{kind}/scanners'
                scanners = self.model_store.list(path + '/*')
                rails.scanners = self._load_tools(scanners, path, instance=False)
        return rails_fns

    def _load_documents(self, documents):
        documents = (
            self.data_store.get(documents, model_store=self.model_store) if isinstance(documents, str) else documents
        )
        return documents

    def _load_pipeline(self, pipeline):
        pipeline = (
            pipeline if callable(pipeline) else (self.model_store.get(pipeline) if isinstance(pipeline, str) else None)
        )
        return pipeline

    def _resolve_placeholders(self, creds, secrets):
        values = (
            {k: v for k, v in os.environ.items() if k.isupper() and isinstance(v, (str, bytes))}
            if self.model_store.defaults.OMEGA_ALLOW_ENV_CONFIG
            else dict()
        )
        values.update(**self.model_store.defaults)
        values.update(secrets)
        user = getattr(self.model_store.defaults, 'OMEGA_USERID', getuser())
        return creds.format_map(KeepMissing({**values, "userid": user}))

    def _infer_provider(self, url):
        for provider, cls in PROVIDERS.items():
            if cls.match_url(url):
                return provider
        return 'default'

    def _ensure_tracking(self, meta):
        # ensure we have a tracking instance for the model
        # caveats:
        # - this is typically a responsibility of the omega runtime, however
        #   a conversation model without a tracking instance is useless
        # - thus we adopt the convention that if the runtime does not provide a tracking instance,
        #   we create one for the model
        # TODO: verify that this is the right place to do this
        default_name = meta.attributes.get('tracking', {}).get('default', meta.kind_meta.get('model'))
        if self.tracking is None or isinstance(self.tracking.experiment, NoTrackTracker):
            self.tracking = OmegaSimpleTracker(default_name, store=self.data_store)
            self.tracking.start()
        return self.tracking


class TextModel(GenAIModel):
    """OpenAI model

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

    .. versionchanged:: 0.18.0
        the ./openai/messages dataset has been replaced by standard experiment tracking
        (use om.datasets to access prior conversations)

    .. versionchanged:: NEXT
        Specify guardrails=list[str] as the name of guardrail functions or GuardrailPolicy objects stored
        in om.models as 'policy/<name>'. Guardrails are evaluated for steps 'prompt', 'input', 'output', 'action',
        'response' and output steps. See GuardrailPolicy for details. Guardrails are evaluated after pipeline hooks
        have completed.

    .. versionchanged:: NEXT
        pipeline functions are now consistently called for all phases of either chat() or complete(), including
        method='retrieve' for document retrieval.

    .. versionchanged:: NEXT
        tool calls are now executed at the end of the core loop, enabling basic agentic behavior,
        see TextModel.complete() for details.

    .. versionchanged:: NEXT
        all logged events are equivalent for .chat() and .complete(). Previously only .chat() logged all conversations.
    """

    def __init__(
            self,
            base_url,
            model,
            api_key=None,
            template=None,
            prompt=None,
            data_store=None,
            tracking=None,
            pipeline=None,
            provider='openai',
            tools=None,
            guardrails=None,
            documents=None,
            strategy=None,
            trace=None,
            **kwargs,
    ):
        super().__init__()
        self.base_url = base_url
        self.model = model
        self.api_key = api_key or 'MISSING_AI_PROVIDER_APIKEY'
        self.kwargs = kwargs
        self.template = (template or self._default_template).strip()
        self.prompt = prompt or 'You are a helpful assistant.'
        self.data_store = data_store
        self.tracking = tracking
        self.provider = PROVIDERS[provider](
            api_key=self.api_key, base_url=self.base_url, model=self.model, tracking=self.tracking
        )
        self.pipeline_fn = pipeline or (lambda *args, **kwargs: None)
        self.trace_fn = trace
        self.tools = tools or []
        self.guardrails = guardrails or []
        self.documents = documents
        self.strategy = {
            # defaults
            **{
                # kwargs to pass to DocumentIndex.retrieve()
                'retrieve': {'top': 1},
                # system role: 'system|developer'
                'system_role': 'developer',
                # agentic behavior: if True, will continue in a loop until no more tool calls
                'agentic': False,
                # guardrails applicability (all is the only supported value)
                'guardrails': 'all',
                # choice of tools
                'tool_choice': 'auto',
                # provider.complete() kwargs
                'complete': {},
            },
            # override by user provided
            **(strategy or {}),
        }

    def __repr__(self):
        return f'TextModel(base_url={self.base_url}, model={self.model})'

    @property
    def _default_template(self):
        return """
        {% if documents -%} 
            consider these documents: {{ documents }} 
        {%- endif %} 
        {{ prompt }}
        """

    def load(self):
        pass

    def trace(self, fn=None, methods=None):
        """trace pipeline calls

        Args:
            fn (callable): a callable, accepting the same arguments as a pipeline function
            methods (list): optional, specify the pipeline methods to trace, e.g. prepare, complete,
               toolprepare, toolcall, toolresult, process

        Returns:
            self
        """
        methods = methods or []

        def tracefn(*args, method=None, **kwargs):
            if not methods or method in methods:
                print(f"tracing method={method}", pformat(kwargs))

        self.trace_fn = fn if callable(fn) else tracefn
        return self

    def embed(self, documents, dimensions=None, raw=False, conversation_id=None, **kwargs):
        dimensions = dimensions or self.kwargs.get('dimensions', 256)
        response = self.provider.embed(documents, dimensions=dimensions, model=self.model, **kwargs)
        conversation_id = conversation_id or uuid4().hex
        self._track_usage(response, conversation_id=conversation_id)
        transformed = (d.get('embedding', d) for d in response.get('data', response))
        return response if raw else list(transformed)

    def complete(
            self,
            prompt,
            messages=None,
            conversation_id=None,
            raw=False,
            data=None,
            chat=False,
            stream=False,
            use_tools=True,
            trace=None,
            agentic=False,
            tools=None,
            **kwargs,
    ):
        """complete a prompt

        Will call the provider's chat.completion endpoint. Can be called in two modes:
        1) completion without conversation tracking (no conversation id, chat=False),
        2) chat completion with conversation tracking (chat=True, or conversation id).

        Args:
            prompt (str|dict|list): the input prompt to pass to the model. A string will
               be converted to an input message; a dict as appended as the last message to all
               messages, a list is assumed to be a list of fully formed messages as required by the
               openai /chat/completions endpoint
            messages (list[dict]): optional, a list of previous messages. If a conversation_id is
               specified and if tracking is enabled, the messages are retrieved from the tracking provider
            conversation_id (str): optional, a unique id for the conversation, defaults to uuid4().hex
            raw (bool): optional, defaults to False. If True returns messages in the original format of the
               provider API. If False returns just the latest response in a simplified format.
            data (dict): optional, if specified will be used to replace {placeholders} in the model's template,
               using template.format_map(data)
            chat (bool): optional, defaults to False. If True will use TextModel.chat() to complete the call. requires a tracking
               provider and a data_store to track all 'conversation' events (input + output messages)
            stream (bool): optional, defaults to False. If True a generator is returned to consume response messages
            use_tools (bool): optional, defaults to True. If True, and tools have been specified for the model, the
               model is asked to choose a tool for execution, and any chosen tool will be executed by TextModel as
               part of the completion. If False, no tools will be provided to the model.
            agentic (bool): optional, defaults to False. If True, will recursively resolve tool calls until no further
                tools are called by the model. This implies tools=True if tools are present. Tool calls are not
                streamed. This can also be set permanently by saving a model with models.put(..., strategy={
                'agentic': True})
            **kwargs:

        Returns:
            response (dict|iterator): if stream==False, returns a dict of all model responses, if stream==True
              returns an iterator of streamed responses.

        .. versionchanged:: NEXT
            TextModel.complete(..., agentic=True) will recursively resolve calls until no further tools are
            called by the model. This implies tools=True if tools are present. Tool calls are not streamed. This
            can also be set permanently by saving a model with models.put(..., strategy={'agentic': True})
        """
        self.trace(trace) if locals().get('trace') else None

        agentic = agentic or self.strategy.get('agentic', False)
        if agentic:
            conversation_id = conversation_id or uuid4().hex
            use_tools = True
        if tools:
            self.tools.extend(tools)

        def parse_completion_response(r):
            response, _, response_message, raw_response = r
            return response_message if not raw else response

        def parse_chat_response(r):
            conversation_id, response, _, response_message, raw_response = r
            return response_message if not raw else response

        def generate_response_stream_once(prompt, messages, use_tools):
            if not chat and conversation_id is None:
                responses = self._do_complete(
                    prompt, messages=messages, data=data, stream=stream, use_tools=use_tools, raw=raw, **kwargs
                )
                response_parser = parse_completion_response
            else:
                # chat or conversation id provided
                responses = self._do_chat(
                    prompt,
                    messages=messages,
                    conversation_id=conversation_id,
                    data=data,
                    stream=stream,
                    use_tools=use_tools,
                    raw=raw,
                    **kwargs,
                )
                response_parser = parse_chat_response
            # return response(s)
            # -- parse, then check if parsed is a valid object (avoid passing on a generator)
            parsed_gen = (response_parser(response) for response in responses)
            response_gen = (parsed for parsed in parsed_gen if isinstance(parsed, (list, dict, tuple)))
            return response_gen

        def generate_response_loop(prompt, messages, use_tools):
            turn_prompt = prompt
            intermediate_results = None
            turn_count = 0
            while True:
                response = None
                tool_calls = None
                turn_count += 1
                # the stream may contain multiple partial toolcall messages
                # -- first, generate the full stream until it stops
                # -- then, check for tool calls across the consolidate stream
                # -- use_tools=True triggers tool choices, actual decision to run below
                try:
                    for response in generate_response_stream_once(turn_prompt, messages, use_tools=True):
                        if not raw and intermediate_results:
                            # FIXME move to conversation state
                            response.setdefault('intermediate_results', []).append(intermediate_results)
                            intermediate_results = None
                        yield response
                        tool_calls = self._has_tool_calls(response, implicit=not raw)
                except Exception as e:
                    logger.warning(f'could not process response due to {e} in {conversation_id=}', exc_info=True)
                    response = {"error": {"message": f"could not process response in {conversation_id=}"}}
                    yield response
                    break
                if response and tool_calls and (agentic or use_tools):
                    intermediate_results, tool_prompts = self._handle_toolcalls(response, tool_calls, conversation_id)
                    turn_prompt = tool_prompts
                    continue
                # abort if no more tool calls, or not agentic
                break

        response_gen = generate_response_loop(prompt, messages, use_tools)
        return response_gen if stream else [response for response in response_gen][-1]

    def chat(self, prompt, conversation_id=None, raw=False, stream=False, use_tools=True, **kwargs):
        """chat completions

        This is the same as TextModel.complete() however ensures a tracking provider and a data_store
        have been made active in order to store and retrieve previous messages.

        Args:
            prompt (str|list|dict): the prompt to use, see Text.complete() for details
            conversation_id (str): the conversation id, used to retrieve previous messages from the
              tracking provider, defaults to uuid4().hex for new conversations
            raw (bool): optional, defaults to False. If True returns messages in the original format of the
               provider API. If False returns just the latest response in a simplified format.
            stream (bool): optional, defaults to False. If True a generator is returned to consume response messages
            use_tools (bool): optional, defaults to True. If True, and tools have been specified for the model, the
               model is asked to choose a tool for execution, and any chosen tool will be executed by TextModel as
               part of the completion. If False, no tools will be provided to the model.
            **kwargs: optional, passed to TextModel.complete()

        Returns:
           response (dict|iterator): if stream==False, returns a dict of all model responses, if stream==True
              returns an iterator of streamed responses.
        """
        responses = self._do_chat(prompt, conversation_id=conversation_id, stream=stream, use_tools=use_tools, **kwargs)

        def response_parser(r):
            (conversation_id, response, prompt_response, response_message, raw_response) = r
            return conversation_id, (response if raw else response_message)

        response_gen = (response_parser(response) for response in responses if response)
        return response_gen if stream else [response for response in response_gen][-1]

    def _do_chat(
            self, prompt, messages=None, conversation_id=None, data=None, use_tools=False, raw=False, stream=False,
            **kwargs
    ):
        assert self.data_store, "chat requires a data_store, specify data_store=om.datasets"
        assert self.tracking, "chat requires a tracking instance, use with om.runtime.experiment(): ... "
        conversation_id = conversation_id or uuid4().hex
        # if the client sends in messages, don't recall past conversations (they are already in messages)
        messages = messages or self.conversation(conversation_id, raw=True)
        system_message_missing = not any(m.get('role') in ('system', 'developer') for m in messages)
        empty = lambda d: d.empty if isinstance(d, pd.DataFrame) else not d
        if empty(messages) or system_message_missing:
            # no message history, insert the system message to start off the conversation)
            messages = [self._system_message(self.prompt, conversation_id=conversation_id)] + (
                messages if messages else []
            )
            self._log_events('conversation', conversation_id, messages)
        responses = self._do_complete(
            prompt,
            messages=messages,
            conversation_id=conversation_id,
            data=data,
            use_tools=use_tools,
            raw=raw,
            stream=stream,
            **kwargs,
        )
        for response in responses:
            response, prompt_message, response_message, raw_response = response
            yield (conversation_id, response, prompt_message, response_message, raw_response)

    def _handle_toolcalls(self, response, tool_calls, conversation_id):
        results, tool_prompts = self._call_tools(tool_calls, conversation_id)
        tool_prompts = (
                self.pipeline(
                    method='toolcall',
                    prompt_message=None,  # FIXME
                    response_message=response,
                    messages=None,  # FIXME
                    tool_prompts=tool_prompts,
                    tool_results=results,
                    template=None,  # FIXME
                    conversation_id=conversation_id,
                )
                or tool_prompts
        )
        return results, tool_prompts

    def _call_tools(self, tool_calls, conversation_id):
        # process tool calls
        tool_results = []
        tool_prompts = []
        for tool_call in tool_calls:
            tool_specs_callables = zip(self.tools_specs(self.tools), self.tools)
            tool_func = tool_call.get('function', {})
            tool_name = tool_func.get('name')
            tool_id = tool_call.get('id', 'invalid_id')
            tool_args = tool_func.get('arguments', '')
            matched_tool = [(ts, tf) for ts, tf in tool_specs_callables if tf.__name__ == tool_name]
            if matched_tool:
                tool, tool_func = matched_tool[0]
                try:
                    tool_args = json.loads(tool_args)
                    # parse e.g. '{"args": ["is 10 correct?"], "kwargs": {}}'
                    if isinstance(tool_args, dict) and "args" in tool_args and "kwargs" in tool_args:
                        real_args = (
                            tuple(tool_args["args"]) if isinstance(tool_args["args"], list) else tool_args["args"]
                        )
                        real_kwargs = tool_args.get("kwargs", {})
                    else:
                        # parse e.g. '{"prompt": "how are you"}'
                        real_args = []
                        real_kwargs = tool_args
                    tool_result = tool_func(*real_args, **real_kwargs)
                except Exception as e:
                    tool_result = str(e)
                tool_result = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
                tool_response = {"role": "tool", "tool_call_id": tool_id, "content": str(tool_result)}
                tool_results.append(tool_result)
                tool_prompts.append(tool_response)
                self._log_events(
                    'toolcall',
                    conversation_id,
                    {
                        'name': tool_name,  # fmt:asis
                        'too_call_id': tool_id,
                        'arguments': tool_args,
                        'result': str(tool_result),
                    },
                )
            else:
                # invalid tool call
                tool_result = 'tool call was invalid'
                tool_response = {"role": "tool", "tool_call_id": tool_id, "content": str(tool_result)}
                tool_results.append(tool_result)
                tool_prompts.append(tool_response)
                self._log_events(
                    'error',
                    conversation_id,
                    {
                        'name': tool_name,  # fmt:asis
                        'too_call_id': tool_id,
                        'arguments': tool_args,
                        'result': str(tool_result),
                    },
                )
        results = {'tool_calls': tool_calls, 'tool_prompts': tool_prompts, 'tool_results': tool_results}
        return results, tool_prompts

    def conversation(self, conversation_id=None, raw=False, **filter):
        """Retrieve conversation messages

        Args:
            conversation_id (str): the conversation id to retrieve messages for
            raw (bool): if True, return raw messages as dicts, otherwise return a DataFrame
            filter (dict): additional filters to apply to the conversation messages

        Returns:
            pd.DataFrame or list[dict]: the conversation messages, either as a DataFrame or a list of dicts
        """
        assert self.data_store, "this model does not track conversations, specify .get(...., data_store=om.datasets)"
        assert self.tracking, "this model does not track conversations, use with om.runtime.experiment(): ... "
        filter.setdefault('run', '*')
        filter.setdefault('key', conversation_id)
        messages = self.tracking.data(event='conversation', **filter)
        if messages is not None and 'value' in messages.columns:
            messages = pd.concat([messages.reset_index(), pd.json_normalize(messages['value'])], axis=1)
            # FIXME fillna('') is deprecated for numeric columns (handle in serialization?)
            messages.fillna('', inplace=True)
            columns = list(set(messages.columns) & {'key', 'role', 'content', 'finish_reason', 'dt'})
            return messages[columns] if not raw else list(messages['value'].to_dict().values())
        return pd.DataFrame() if not raw else []

    def pipeline(self, *args, **kwargs):
        self.trace_fn(*args, **kwargs) if callable(self.trace_fn) else None
        kwargs['model'] = self
        return self.pipeline_fn(*args, **kwargs) or False

    def tools_specs(self, tools):
        return [self._get_function_spec(tool) for tool in tools]

    def _system_message(self, prompt, conversation_id=None):
        return {
            "role": self.strategy['system_role'],
            "content": prompt,
            "conversation_id": conversation_id or uuid4().hex,
        }

    def _do_complete(
            self, prompt, messages=None, conversation_id=None, data=None, stream=False, use_tools=False, raw=False,
            **kwargs
    ):
        conversation_id = conversation_id or uuid4().hex
        messages = messages or []
        kwargs.update(self.strategy.get('complete', {}))
        kwargs.update(stream=stream)
        # prepare tools
        if self.tools:
            kwargs.update(tools=self.tools_specs(self.tools), tool_choice=self.strategy.get('tool_choice', 'auto'))
        # prepare template
        _template = self._prepare_template(self.template, data=data)
        template = (
                self.pipeline(
                    method='template',
                    prompt_message=prompt,
                    messages=messages,
                    template=self.template,
                    conversation_id=conversation_id,
                    **kwargs,
                )
                or _template
        )
        self.eval_guardrails(messages, 'prompt', conversation_id=conversation_id)
        if prompt and isinstance(prompt, str):
            # support direct text input
            prompt_message = {"role": "user", "content": prompt, "conversation_id": conversation_id}
            messages.insert(0, self._system_message(self.prompt, conversation_id=conversation_id))
            messages += [self._augment_message(prompt_message, documents=self.documents, template=template)]
        elif isinstance(prompt, dict):
            # support structured input
            # -- see OpenAI /chat/completions endpoint, "messages" parameter
            #    https://platform.openai.com/docs/api-reference/chat
            # -- assume prompt is a fully formed provider-compatible message,e.g. from a chat client
            messages.insert(0, self._system_message(self.prompt, conversation_id=conversation_id))
            messages += [self._augment_message(prompt, documents=self.documents, template=template)]
            prompt_message = messages[-1]
        elif isinstance(prompt, list):
            # support structured input, as messages
            # -- see OpenAI /chat/completions endpoint, "messages" parameter
            #    https://platform.openai.com/docs/api-reference/chat
            # -- assume prompt is a fully formed provider-compatible message,e.g. from a chat client
            messages.insert(0, self._system_message(self.prompt, conversation_id=conversation_id))
            # augment last message only
            messages += prompt[:-1] if len(prompt) > 1 else []
            messages += [self._augment_message(prompt[-1], documents=self.documents, template=template)]
            prompt_message = messages[-1]
        else:
            # raw input, assume messages contains the user prompt
            messages.insert(0, self._system_message(self.prompt, conversation_id=conversation_id))
            # augment last message only
            messages[-1] = self._augment_message(messages[-1], documents=self.documents, template=template)
            prompt_message = messages[-1]
        # prepare messages
        _default_messages = messages
        messages = (
                self.pipeline(
                    method='prepare',
                    prompt_message=prompt_message,
                    messages=messages,
                    template=template,
                    conversation_id=conversation_id,
                    **kwargs,
                )
                or _default_messages
        )
        self.eval_guardrails(messages, 'input', conversation_id=conversation_id)
        # produce a response by calling the pipeline or the model
        response = self.pipeline(
            method='complete',
            prompt_message=prompt_message,
            messages=messages,
            template=template,
            conversation_id=conversation_id,
            **kwargs,
        )
        # finally call the model provider, if needed
        self._log_events('conversation', conversation_id, prompt_message)
        response = response or self.provider.complete(messages=messages, model=self.model, **kwargs)

        def capture_tool_calls(
                response, prompt_message, response_message, use_tools=False, as_delta=False, chunks=None
        ):
            """capture toolcalls across stream messages to consolidate into a single, fully formatted toolcall

            Combines previously streamed 'tool_calls' messages into a properly formatted, combined tool call. This
            is because tool calls can be sent as partial specifications across several streamed messages

            See Also:
                - https://developers.openai.com/api/docs/guides/function-calling#streaming
                - https://www.perplexity.ai/search/718b5969-fce4-4ad6-bd4b-e1fe66de9d8e
            """
            tool_message = self._get_response_message(response_message)
            should_call = self._get_finish_reason(response) == 'tool_calls'
            if should_call and self.tools:
                if chunks:
                    # consolidate previous chunks, if any
                    # -- in streaming mode, tool_calls can be sent in multiple chunks
                    # -- merge partial tool_calls by index
                    tool_calls_map = {}
                    chunked_msgs = (self._get_response_message(c) for c in chunks)
                    chunked_calls = (c.get('tool_calls') for c in chunked_msgs if 'tool_calls' in c)
                    partial_calls = chain.from_iterable(c for c in chunked_calls)
                    for partial_call in partial_calls:
                        idx = partial_call.get('index', 0)
                        tool_calls_map.setdefault(idx, tool_message.get('tool_calls') or {})
                        dict_merge(tool_calls_map[idx], partial_call)
                    # -- finalize tool call message
                    tool_calls = list(sorted(tool_calls_map.values(), key=lambda v: v.get('index')))
                else:
                    tool_calls = tool_message.get('tool_calls')
                if use_tools and tool_calls:
                    tool_calls = (
                            self.pipeline(
                                method='toolprepare',
                                prompt_message=prompt_message,
                                response_message=response_message,
                                messages=messages,
                                tool_calls=tool_calls,
                                template=template,
                                conversation_id=conversation_id,
                                **kwargs,
                            )
                            or tool_calls
                    )
                    response_message['tool_calls'] = tool_calls
                    self.eval_guardrails(messages + [response_message], 'action', conversation_id=conversation_id)
            return response, prompt_message, response_message

        def resolve_response(response, prompt_message, use_tools=False):
            raw_response = response.to_dict() if hasattr(response, 'to_dict') else response
            if len(raw_response['choices']) == 0:
                # this should not happen per the protocol - if it does, simulate an empty delta
                raw_response['choices'].append({'message': {'content': None}})
            if 'error' in response:
                return (
                    response,
                    prompt_message,
                    {
                        "role": "system",
                        "content": response['error'].get('message', str(response['error'])),
                        "conversation_id": conversation_id,
                        "error": response['error'],
                    },
                    raw_response,
                )
            response_message = response['choices'][0]['message']
            self.eval_guardrails(messages + [response_message], 'response', conversation_id=conversation_id)
            response_message.setdefault('conversation_id', conversation_id)
            response, prompt_message, response_message = capture_tool_calls(
                response, prompt_message, response_message, use_tools=use_tools
            )
            response_message = (
                    self.pipeline(
                        method='process',
                        response_message=response_message,
                        prompt_message=prompt_message,
                        messages=messages,
                        template=template,
                        conversation_id=conversation_id,
                        **kwargs,
                    )
                    or response_message
            )
            self.eval_guardrails(messages + [response_message], 'output', conversation_id=conversation_id)
            return response, prompt_message, response_message, raw_response

        def resolve_chunk(response, chunk, chunks, prompt_message, consolidated_response, use_tools=False):
            """resolve a single chunk of a streamed response

            Args:
                response (OpenAIResponse): the full response object
                chunk (OpenAIResponseChunk): the current chunk of the response
                chunks (list): list of all chunks received so far
                prompt_message (dict): the prompt message used for this request
                consolidated_response (dict): the consolidated response so far
                use_tools (bool): whether to use tools in this response

            Returns:
                tuple: (response, prompt_message, response_message, raw_response)

                where:
                    response: the full response object
                    prompt_message: the prompt message used for this request
                    response_message: the response message as a dictionary (choices[0].delta)
                    raw_response: the raw response chunk as a dictionary

            """
            raw_response = chunk.to_dict() if hasattr(chunk, 'to_dict') else chunk
            # consolidate content
            content = ''.join(
                c['choices'][0]['delta'].get('content') or ''  # fmt:asis
                for c in chunks
            ) + str(chunk['choices'][0]['delta'].get('content') or '')
            reasoning = ''.join(
                c['choices'][0]['delta'].get('reasoning') or ''  # fmt:asis
                for c in chunks
            ) + str(chunk['choices'][0]['delta'].get('reasoning') or '')
            if chunk['choices']:
                if raw:
                    response_message = chunk['choices'][0]['delta']
                else:
                    response_message = {
                        "role": chunk['choices'][0]['delta'].get('role'),
                        "delta": chunk['choices'][0]['delta'].get('content'),
                        'reasoning': reasoning,
                        "content": content,
                        "conversation_id": conversation_id,
                        "tool_calls": chunk['choices'][0]['delta'].get('tool_calls'),
                        "finish_reason": chunk['choices'][0].get('finish_reason'),
                    }
                    # response_message.update(consolidated)
                response_message.setdefault('conversation_id', conversation_id)
                response, prompt_message, response_message = capture_tool_calls(
                    chunk, prompt_message, response_message, use_tools=use_tools, as_delta=True, chunks=chunks
                )
                response_message = (
                        self.pipeline(
                            method='process',
                            response_message=response_message,
                            prompt_message=prompt_message,
                            messages=messages,
                            template=template,
                            conversation_id=conversation_id,
                            **kwargs,
                        )
                        or response_message
                )
                self.eval_guardrails(messages, 'response', conversation_id=conversation_id)
            else:
                content = ''
            # consolidate response
            consolidated_response.update({'content': content, 'reasoning': reasoning})
            consolidated_response.update(response_message)
            chunks.append(raw_response)
            return response, prompt_message, response_message, raw_response

        if stream:
            chunks = []
            consolidated_response = {}
            # -- wrap generator in try/finally to ensure we capture consolidated response even if client aborts
            try:
                for chunk in response:
                    try:
                        self._track_usage(chunk, conversation_id)
                        resolved = resolve_chunk(
                            response, chunk, chunks, prompt_message, consolidated_response, use_tools=use_tools
                        )
                    except Exception as e:
                        logger.warning(f"could not process chunk {chunk.get('id')} due to {e}", exc_info=True)
                        self._log_events(
                            'error', conversation_id, f'could not process stream chunk due to {e} {chunk=}'
                        )
                        response_message = {
                            'error': {'message': f'could not process stream chunk for {conversation_id=}'}
                        }
                        consolidated_response.update(response_message)
                        self.eval_guardrails(
                            messages + [consolidated_response], 'output', conversation_id=conversation_id
                        )
                        yield response, prompt_message, response_message, response_message
                    else:
                        self.eval_guardrails(
                            messages + [consolidated_response], 'output', conversation_id=conversation_id
                        )
                        yield resolved
            finally:
                # log consolidated response only
                if consolidated_response:
                    self._log_events('conversation', conversation_id, consolidated_response)
        else:
            try:
                self._track_usage(response, conversation_id)
                yield resolve_response(response, prompt_message, use_tools=use_tools)
            except Exception as e:
                logger.warning(f"Could not process chunk {response.get('id')} due to {e}")
                self._log_events('error', conversation_id, [response])
                response_message = {'error': {"message": f'could not process chunk for {conversation_id=}'}}
                self.eval_guardrails(messages + [response_message], 'output', conversation_id=conversation_id)
                yield response, prompt_message, response_message, response_message
            finally:
                self._log_events('conversation', conversation_id, self._get_response_message(response))

    def eval_guardrails(self, messages, step, conversation_id=None):
        try:
            for rails in self.guardrails:
                eval_fn = getattr(rails, 'eval', rails)
                result = eval_fn(messages, step=step, model=self)
                result = getattr(rails, 'data', result)
        except Exception as e:
            result = {'error': {'message': str(e)}}
            raise e
        finally:
            if self.guardrails:
                self._log_events('guardrails', conversation_id, result)

    def _parsed_completion(self, response):
        return response['choices'][0]['message'].get('content')

    def _prepare_template(self, template, data=None):
        _template = (template or '').format_map(safeformat(data or {}))
        return template

    def _get_response_message(self, response):
        # return the current response message or chunk
        if 'role' in response or 'error' in response:
            # that's already a message
            return response
        if 'delta' in response['choices'][0]:
            message = response['choices'][0]['delta']
        else:
            message = response['choices'][0]['message']
        return message

    def _get_finish_reason(self, response):
        return response.get('choices', [{}])[-1].get('finish_reason')

    def _has_tool_calls(self, response, implicit=False):
        message = self._get_response_message(response)
        finish_reason = self._get_finish_reason(response)
        tool_calls = message.get('tool_calls', [])
        return tool_calls if (finish_reason == 'tool_calls' or implicit) else False

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
        TYPES = {str: 'string', int: 'integer', float: 'float', list: 'list'}
        for param in sig.parameters.values():
            param_type = (
                TYPES.get(param.annotation) or 'string' if param.annotation != inspect.Parameter.empty else None
            )
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
                "parameters": {"type": "object", "properties": {k: v for k, v in params.items()}},
                "return_type": return_type,
            },
        }

        return function_dict

    def _augment_prompt(self, prompt, documents: DocumentIndex = None, query=None, template=None):
        query = query or prompt
        template = template or self.template
        if not documents:
            context = dict(prompt=prompt, query=query, documents=None, datetime=utcnow())
            return self._resolve_template(template, **context)
        retrieve_kwargs = self.strategy.get('retrieve', {})
        if documents:
            docs = documents.retrieve(query, **retrieve_kwargs)
        else:
            docs = []
        docs = (
                self.pipeline(
                    method='retrieve',
                    prompt_message=prompt,
                    messages=None,  # FIXME
                    docs=docs,
                    template=template,
                )
                or docs
        )
        if docs:
            retrieved = '\n\n'.join(str(d.get('text') if isinstance(d, dict) else d) for d in docs)
        elif documents:
            retrieved = '(no documents found)'
        else:
            retrieved = None
        context = dict(prompt=prompt, query=query, documents=retrieved, datetime=utcnow())
        return self._resolve_template(template, **context)

    def _resolve_template(self, template, **context):
        env = SandboxedEnvironment()
        template = env.from_string(template)
        return template.render(**context).strip()

    def _augment_message(self, message, documents: DocumentIndex = None, query=None, template=None):
        augmented = self._augment_prompt(
            message.get('content', ''), documents=documents, query=query, template=template
        )
        message['content'] = augmented if augmented else message.get('content')
        return message

    def _log_events(self, event, conversation_id, data):
        if self.tracking:
            self.tracking.log_events(event, conversation_id, ensure_list(data))
            self.tracking.flush()

    def _track_usage(self, response, conversation_id):
        data = ensure_dict(response)
        if self.tracking:
            for metric, value in data.get('usage', {}).items():
                self.tracking.log_event('usage', metric, value, conversation_id=conversation_id)


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


class safeformat(dict):
    def __missing__(self, key):
        return f"{{{key}}}"  # return "{<key>}"
