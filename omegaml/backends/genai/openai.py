from collections import namedtuple
from uuid import uuid4

import re
from openai import OpenAI
from urllib.parse import urlparse, parse_qs

from omegaml.backends.genai.base import GenAIBaseBackend, GenAIModel
from omegaml.store import OmegaStore


class OpenAIModelBackend(GenAIBaseBackend):
    KIND = 'genai.openai'

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

    def put(self, obj, name, template=None, pipeline=None, **kwargs):
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
        kind_meta = {
            'base_url': base_url,
            'creds': creds,
            'model': model,
            'query': query,
            'params': params,
        }
        attributes = {
            'template': template,
            'dataset': self._messages_dataset(name),
            'pipeline': pipeline or None,
        }
        kwargs.update(attributes=attributes)
        meta = self.model_store.make_metadata(name,
                                              kind=self.KIND,
                                              kind_meta=kind_meta,
                                              **kwargs)
        return meta.save()

    def get(self, name, template=None, data_store=None, **kwargs):
        meta = self.model_store.metadata(name)
        kind_meta = meta.kind_meta
        base_url = kind_meta['base_url']
        model = kind_meta['model']
        query = kind_meta['query']
        params = kind_meta['params']
        creds = kind_meta['creds']
        pipeline = meta.attributes.get('pipeline')
        params.update(kwargs)
        template = template or meta.attributes.get('template')
        data_store = data_store or (self.data_store if self.data_store is not self.model_store else None)
        pipeline = self.model_store.get(pipeline) if pipeline else None
        return OpenAIModel(base_url, model, api_key=creds, template=template,
                           data_store=data_store, pipeline=pipeline,
                           dataset=self._messages_dataset(name, meta=meta),
                           **params)

    def drop(self, name, data_store=None, force=False, **kwargs):
        meta = self.model_store.metadata(name)
        data_store = data_store or (self.data_store if self.data_store is not self.model_store else None)
        if data_store:
            self.data_store.drop(self._messages_dataset(name, meta=meta), force=force, **kwargs)
        return self.model_store._drop(name, force=force, **kwargs)

    def _messages_dataset(self, name, meta=None):
        return f'./openai/messages/{name}' if meta is None else meta.attributes.get('dataset')


class OpenAIModel:
    def __init__(self, base_url, model, api_key=None, template=None, data_store=None,
                 dataset=None, pipeline=None, **kwargs):
        super().__init__(**kwargs)
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.kwargs = kwargs
        self.template = template or 'You are a helpful assistant.'
        self.data_store = data_store
        self.dataset = dataset
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url)
        self.pipeline = pipeline or (lambda *args, **kwargs: None)

    def load(self, method):
        pass

    def complete(self, prompt, messages=None, conversation_id=None, raw=False, data=None, **kwargs):
        if conversation_id is None:
            response, _, response_message = self._do_complete(prompt, messages=messages, data=data, **kwargs)
        else:
            conversation_id, response, _, response_message = self._do_chat(prompt, conversation_id=conversation_id,
                                                                           data=data,
                                                                           **kwargs)
        return response_message if raw else response_message

    def chat(self, prompt, conversation_id=None, raw=False, **kwargs):
        conversation_id, response, *_ = self._do_chat(prompt,
                                                      conversation_id=conversation_id,
                                                      **kwargs)
        return conversation_id, (response if raw else self._parsed_completion(response))

    def _do_chat(self, prompt, conversation_id=None, data=None, **kwargs):
        assert self.data_store, "chat requires a data_store, specify data_store=om.datasets"
        conversation_id = conversation_id or uuid4().hex
        messages = self.conversation(conversation_id)
        if hasattr(messages, 'to_dict'):
            # convert pandas dataframe to records
            messages = messages.to_dict('records')
        if messages is None:
            messages = [self._system_message()]
            self.data_store.put(messages, self.dataset, kind='pandas.rawdict')
        resp = self._do_complete(prompt, messages, conversation_id=conversation_id, data=data, **kwargs)
        response, prompt_message, response_message = resp
        to_store = [
            prompt_message,
            response_message
        ]
        self.data_store.put(to_store, self.dataset, kind='pandas.rawdict')
        return conversation_id, response, prompt_message, response_message

    def conversation(self, conversation_id, raw=False):
        if conversation_id is None:
            filter = {}
        else:
            filter = {'conversation_id': conversation_id}
        messages = self.data_store.get(self.dataset, **filter)
        return messages if not raw else messages.to_dict('records')

    def _system_message(self, conversation_id=None):
        return {
            "role": "system",
            "content": self.template,
            "conversation_id": conversation_id or uuid4().hex,
        }

    def _do_complete(self, prompt, messages=None, conversation_id=None, data=None, **kwargs):
        messages = messages or [self._system_message()]
        prompt_message = {
            "role": "user",
            "content": prompt,
            "conversation_id": conversation_id or uuid4().hex,
        }
        _template = self._prepare_template(self.template,
                                          data=data)
        template = self.pipeline(method='template', conversation_id=None,
                                 prompt_message=prompt_message,
                                 messages=messages,
                                 template=self.template, data=data, **kwargs) or _template
        messages = self.pipeline(method='prepare',
                                 prompt_message=prompt_message,
                                 messages=messages,
                                 template=template,
                                 conversation_id=conversation_id, **kwargs) or messages
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages + [prompt_message],
            **kwargs
        )
        response_message = {
            "role": response.choices[0].message.role,
            "content": response.choices[0].message.content,
            "conversation_id": conversation_id or uuid4().hex,
        }
        response_message = self.pipeline(method='process', response_message=response_message,
                                         prompt_message=prompt_message,
                                         messages=messages,
                                         template=template,
                                         conversation_id=conversation_id,
                                         **kwargs) or response_message
        return response, prompt_message, response_message

    def _parsed_completion(self, response):
        return response.choices[0].message.content

    def _prepare_template(self, template, data=None):
        _template = (template or '').format(**(data or {}))
        return template