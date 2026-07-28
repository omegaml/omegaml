from unittest import TestCase
from uuid import uuid4

from omegaml.backends.genai.eventagent import EventAgent
from omegaml.backends.genai.textmodel import TextModel, Provider
from omegaml.tests.util import OmegaTestMixin


class ConversationReplay:
    def __init__(self, messages=None, sessionid=None, target=None):
        self.messages = messages or []
        self.sessionid = str(sessionid or uuid4().hex)
        # assume messages are in (role=user, role=assistant) sequence
        for msg_user, msg_assistant in zip(self.messages[:-1], self.messages[1:]):
            self.add(msg_user.get('content'), msg_assistant.get('content'))
        self.apply(target) if target is not None else None

    def apply(self, target):
        if isinstance(target, EventAgent):
            target._model = self
        if isinstance(target, TextModel):
            target.provider = self.as_provider()

    def add(self, prompt, response, messages=None):
        if isinstance(response, str):
            response = {'choices': [{'message': {'role': 'assistant', 'content': response}}]}
        self.messages.append({'prompt': prompt, 'response': response})

    def chat(self, prompt, messages=None, *args, **kwargs):
        resp = self.complete(prompt, messages=messages, *args, **kwargs)
        resp['conversation_id'] = self.sessionid
        return self.sessionid, resp

    def complete(self, prompt, messages=None, *args, **kwargs):
        for spec in self.messages:
            if prompt.endswith(spec['prompt']):
                return spec['response']
        return {'choices': [{'message': {'role': 'assistant', 'content': 'hello'}}]}

    def as_provider(self):
        this = self

        class ReplayProvider(Provider):
            def complete(self, model, messages, stream=False, **kwargs):
                return this.complete(messages[-1].get('content'), messages=messages)

        return ReplayProvider(api_key='dummykey', base_url='http://localhost/api')


class EvenAgentTests(OmegaTestMixin, TestCase):
    def setUp(self):
        super().setUp()

    def test_model_flow(self):
        om = self.om
        meta = om.models.put('openai+http://localhost;model=mymodel', 'mymodel', replace=True)

        agent = EventAgent(model='mymodel')
        replay = ConversationReplay(target=agent)
        replay.add('hello', 'Hello! How can I help you?')

        resp = agent.invoke('hello')
        self.assertEqual(resp['final_output'], 'Hello! How can I help you?')
