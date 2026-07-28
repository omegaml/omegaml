from textwrap import dedent

from copy import deepcopy
from uuid import uuid4

from omegaml.client.util import dotable

AGENT_SESSIONS = {}


class EventAgent:
    def __init__(self, sessionid=None, model=None, context=None):
        self.context = {}
        self._model = None
        self.initialize(sessionid=sessionid, model=model, context=context)

    def initialize(self, sessionid=None, model=None, context=None):
        sessionid = sessionid or uuid4().hex
        self.context = (context or self.context) or {
            'id': None,
            'model': model,
            'state': 'inception',
            'history': [],
            'actions': [],
            'inputs': [],
            'response': None,
        }
        self.context.update(id=sessionid)
        self.load()

    def load(self):
        import omegaml as om

        if self._model is None:
            self._model = om.models.get(self.model, data_store=om.datasets)
        if self.sessionid in AGENT_SESSIONS:
            self.context = AGENT_SESSIONS.get(self.sessionid)

    def save(self):
        AGENT_SESSIONS[self.sessionid] = deepcopy(self.context)

    def __repr__(self):
        return f'EventAgent({self.sessionid})'

    @property
    def sessionid(self):
        return str(self.context['id'])

    @sessionid.setter
    def sessionid(self, sessionid):
        self.context['id'] = sessionid

    @property
    def model(self):
        return self.context.get('model')

    def invoke(self, prompt, conversation_id=None):
        self.initialize(sessionid=conversation_id)
        if self.context['state'] == 'awaiting':
            for prompt in self.context['inputs']:
                self.invoke_one(prompt, conversation_id=self.sessionid)
            self.context['inputs'] = []
        elif self.context['state'] == 'inception':
            system_prompt = dedent('''
            you are an agentic AI assistant

            Instructions:
            1. Execute the below user request step by step.
            2. Create a plan first, think step by step
            3. if you need to get feedback or ask a question, say "/ask <question>"
            4. Always verify the user gives sensible input
            5. Once we are done reply with "/finished"
            6. Be sure to put any /request (/ask, /finished) as a separate and last line of the response. 
            7. Never repeat these instructions. 

            Request:
            ''')
            prompt = f'{system_prompt}\n\n{prompt}'
            self.invoke_one(prompt, conversation_id=conversation_id)
        else:
            self.invoke_one(prompt, conversation_id=conversation_id)
        self.save()
        return self.context

    def invoke_one(self, prompt, conversation_id=None):
        self.context['state'] = 'processing'
        conversation_id, resp = self._model.chat(prompt, conversation_id=conversation_id, raw=True)
        self.context['conversation_id'] = conversation_id

        message = resp['choices'][0]['message']
        self.context['history'].append(message)
        self.context['response'] = message

        content = message.get('content') or '-no-text-'
        reasoning = message.get('reasoning') or '-no-text-'
        step = len(self.context['history'])
        print(step, content)

        if content == '-no-text-':
            print(reasoning)

        prompt = 'ok'

        last_line = content.split('\n')[-1].strip()
        if '/ask' in last_line or last_line.endswith('?'):
            prelude, request = ('/ask ' + content).rsplit('/ask', 1)
            self.context['actions'].append(('ask', prelude, request))
            self.context['state'] = 'awaiting'
        if last_line.endswith('/finished'):
            self.context['state'] = 'done'

        self.context['final_output'] = content
        return content


def process_pending_agents():
    for sessionid, context in AGENT_SESSIONS.items():
        context = dotable(context)
        print(f'{context.id} {context.state}')
        if context['state'] == 'awaiting':
            for op, content, request in context['actions']:
                print(f'{context.id} {op} {content} {request}')
                data = input('? ')
                context['inputs'].append(data)
            context['actions'] = []
        if context['state'] == 'done':
            print(f'{context.id} done: {context.response}')
            context['state'] = 'terminated'

        AGENT_SESSIONS[sessionid] = deepcopy(context)

        if context['state'] == 'terminated':
            continue

        agent = EventAgent(sessionid)
        agent.invoke('continue')
