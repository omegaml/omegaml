from uuid import uuid4

from omegaml.backends.genai.eventagent import EventAgent
from omegaml.backends.genai.textmodel import TextModel, Provider
from omegaml.backends.genai.tools import response_for_toolcalls


class ConversationReplay:
    def __init__(self, messages=None, sessionid=None, target=None):
        self.messages = messages or []
        self.sessionid = str(sessionid or uuid4().hex)
        self.target = target
        # assume messages are in (role=user, role=assistant) sequence
        for msg_user, msg_assistant in zip(self.messages[:-1], self.messages[1:]):
            self.add(msg_user.get('content'), msg_assistant.get('content'))
        self.apply(target) if target is not None else None

    def apply(self, target):
        self.target = target

        if isinstance(target, EventAgent):
            self.model = target._model
            target._model = self  # noqa self is duck typing TextModel.chat(), TextModel.complete()
        if isinstance(target, TextModel):
            self.model = target
            target.provider = self.as_provider()  # noqa self is duck typing Provider.complete()

    def add(self, prompt, response=None, messages=None, tool_calls=None):
        """add a prompt and its response to the list of replayable messages

        Args:
            prompt (str): the prompt, will be matched to actual_prompt.endswith(prompt)
            response (str|dict): the response, if dict must be in openai-completions format,
                {'choices': [{'message': {'role': 'assistant', 'content': 'text'}}]}
            messages (list): optional, not currently used
            tool_call (list): list of tool calls as (fn:function, (args:tuple, kwargs:dict))

        Returns:
            dict: openai-formatted tool_calls response
        """
        if isinstance(response, str):
            response = {'choices': [{'message': {'role': 'assistant', 'content': response}}]}
        if tool_calls:
            response = response_for_toolcalls(tool_calls)
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
