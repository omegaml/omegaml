import logging
import os
import re
from collections import namedtuple
from getpass import getuser
from urllib.parse import parse_qs, urlsplit

from omegaml.backends.genai import GenAIBaseBackend, GenAIModel
from omegaml.backends.genai.providers import PROVIDERS
from omegaml.backends.genai.strategy.augment import AugmentationMixin
from omegaml.backends.genai.strategy.chat import ChatMixin
from omegaml.backends.genai.strategy.completions import CompletionsMixin
from omegaml.backends.genai.strategy.embeddings import EmbeddingsMixin
from omegaml.backends.genai.strategy.toolcalling import ToolCallingMixin
from omegaml.backends.genai.strategy.tracing import TracingMixin
from omegaml.backends.tracking import NoTrackTracker, OmegaSimpleTracker
from omegaml.store import OmegaStore
from omegaml.util import KeepMissing, raise_

logger = logging.getLogger(__name__)


class ConversationModelBackend(GenAIBaseBackend):
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

    KIND = 'genai.convs'
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
               omegaml.genai.providers.PROVIDERS)
            tools (list): optional, the list of tool names stored in om.models
            documents (str): optional, the name of a document store stored in om.datasets
            strategy (dict): optional, kwargs to various parts of the pipeline ('retrieve', 'complete', 'agentic')
            apikey (str): optional, the api key to use, if <credentials> is not part of the URL
            **kwargs:

        Returns:
            metadata (Metadata): the Conversation's metadata object

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
            'tools': tools or [],
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
            documents=None,
            strategy=None,
            tracking=None,
            secrets=None,
            **kwargs,
    ):
        """get a ConversationModel

        Args:
            name (str): the name of the model, as stored using om.models.put()
            prompt (str): optional, the system prompt to use, defaults to metadata.attributes.prompt
            template (str): optional, the template to use for input prompts, defaults ot metadata.attributes.template
            data_store (OmegaStore): optional, the datastore to use for tracking and document stores
            pipeline (str): optional, the name of the @virtualobj pipeline stored in om.models, defaults to
               metadata.attributes.pipeline
            tools (list): optional, the list of tool names stored in om.models
            documents (str): optional, the list of document stores in om.datasets, if specified requires passing
               of data_store=, defaults to metadata.attributes.tools
            strategy (dict): optional, see .put()
            tracking (TrackingProvider): optional, a tracking provider
            secrets (dict): optional, used to resolve {PLACEHOLDERS} in the model's url
            **kwargs:

        Returns:
            model (ConversationModel): the instance of ConversationModel
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
        tools = tools or meta.attributes.get('tools') or []
        documents = documents or meta.attributes.get('documents')
        template = template or query.get('template') or meta.attributes.get('template')
        prompt = prompt or query.get('prompt') or meta.attributes.get('prompt')
        strategy = {**(meta.attributes.get('strategy') or {}), **(strategy or {})}
        # load dependencies
        data_store = data_store or (self.data_store if self.data_store is not self.model_store else None)
        pipeline = self._load_pipeline(pipeline)
        documents = self._load_documents(documents)
        tools = self._load_tools(tools)
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
                        documents=documents,
                        strategy=strategy,
                        tracking=self.tracking,
                    ),
                    **params,
                },
            )

        else:
            model = ConversationModel(
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

    def _load_tools(self, tools):
        barename = lambda v: 'tools/{v}'.format(v=str(v).replace('tools/', ''))  # works with or without tools/ prefix
        verify = lambda t, fn: callable(fn) or raise_(ValueError(f'tool >{t}< is not a callable, got {fn}'))
        tool_fns = [tool if callable(tool) else self.model_store.get(f'{barename(tool)}') for tool in tools]
        tool_fns = [fn for tool, fn in zip(tools, tool_fns) if verify(tool, fn)]
        return tool_fns

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


class ConversationModel(TracingMixin, ToolCallingMixin, AugmentationMixin, EmbeddingsMixin, ChatMixin, CompletionsMixin,
    GenAIModel):
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
        self.documents = documents
        self.strategy = {
            # defaults
            **{
                # kwargs to pass to DocumentIndex.retrieve()
                'retrieve': {'top': 1},
                # system role
                'system_role': 'developer',
                # agentic behavior
                'agentic': False,
            },
            # override by user provided
            **(strategy or {}),
        }

    def __repr__(self):
        return f'ConversationModel(base_url={self.base_url}, model={self.model})'

    def load(self):
        pass
