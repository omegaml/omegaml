from copy import deepcopy
from textwrap import dedent
from uuid import uuid4

from omegaml.backends.genai.memory import EpisodeMemory
from omegaml.backends.genai.models import ConversationModel
from omegaml.backends.specsobj import SpecsBackend, SpecsMixin
from omegaml.backends.tracking import OmegaSimpleTracker
from omegaml.client.util import dotable
from omegaml.util import ensure_list


class EventAgent(SpecsMixin):
    name: str
    sessionid: str
    model: str
    memory: str
    tracking: OmegaSimpleTracker

    def __init__(self, name=None, sessionid=None, model=None, context=None, tracking=None, memory=None, **kwargs):
        self.context = context or {}
        self.tracking = tracking
        self._model: ConversationModel = None
        self._memory: EpisodeMemory = None
        super().__init__(name=name, sessionid=sessionid, model=model, memory=memory, **kwargs)

    def __call__(self, method=None, data=None, conversation_id=None, **kwargs):
        if method == 'invoke':
            return self.invoke(data, conversation_id=conversation_id)

    def __repr__(self):
        name, sessionid = self.name, self.sessionid
        return f'EventAgent({name=}, {sessionid=})'

    def initialize(self, load=False, **kwargs):
        super().initialize(load=False, **kwargs)
        self.sessionid = self.sessionid or uuid4().hex
        self.name = self.name or uuid4().hex
        self.memory = self.memory or self.name
        self.context = {
            'id': self.sessionid,
            'name': self.name,
            'model': self.model,
            'memory': self.memory,
            'state': 'inception',
            'history': [],
            'actions': [],
            'inputs': [],
            'response': None,
        }
        self.load() if load else None

    def load(self):
        import omegaml as om

        if self.tracking is None:
            self.tracking = om.runtime.experiment(self.name)
        if self.sessionid:
            # self.context = AGENT_SESSIONS.get(self.sessionid)
            data = self.tracking.data(event='agent:session', key=self.sessionid)
            self.context = data.iloc[-1]['value'] if data is not None and not data.empty else self.context
        if self._model is None:
            self._model = om.models.get(self.model, data_store=om.datasets)
            self._model.tools.append(self.handoff_to_agent)
            self._model.tools.append(self.handoff_to_human)
        if self._memory is None:
            self.context.setdefault('memory', self.name)
            self._memory = EpisodeMemory(self.context.get('memory'), data_store=self._model.data_store)
            self._model.tools.append(self._memory.memory_tool)

    def save(self):
        # AGENT_SESSIONS[self.sessionid] = deepcopy(self.context)
        with self.tracking:
            self.tracking.log_event('agent:session', self.sessionid, self.context)

    def __repr__(self):
        return f'EventAgent({self.sessionid})'

    def conversation(self, conversation_id=None, raw=False, **filter):
        return self._model.conversation(conversation_id=conversation_id, raw=raw, **filter)

    def sessions(self, raw=False, load=False):
        load = False if raw else load
        data = self.tracking.data(event='agent:session', run='*')
        agents = (
            EventAgent(model=self.model, name=self.name, sessionid=sessionid, load=load)
            for sessionid in data['key'].unique()
        )
        return data.to_dict('records') if raw else list(agents)

    def invoke(self, prompt, conversation_id=None):
        self.initialize(sessionid=conversation_id or self.sessionid, load=True)
        if self.context['state'] in 'awaiting':
            self.handle_deferred_actions()
            for action, response in self.iter_responses():
                message = self.invoke_one(response, conversation_id=self.sessionid)
                self.update_action_state(action, 'processed')
        elif self.context['state'] == 'inception':
            system_prompt = dedent('''
            you are an agentic AI assistant
            ''')
            prompt = f'{system_prompt}\n\n{prompt}'
            message = self.invoke_one(prompt, conversation_id=self.sessionid)
        else:
            message = self.invoke_one(prompt, conversation_id=self.sessionid)
        self.save()
        return message

    def invoke_one(self, prompt, conversation_id=None):
        # -- call model
        self.context['state'] = 'processing'
        self.context['conversation_id'] = conversation_id
        resp = self._model.complete(prompt, conversation_id=conversation_id, raw=True, use_tools=False)
        # process response
        message = resp['choices'][0]['message']
        self.context['history'].append({
            'input': prompt,
            'response': message,
        })
        self.context['response'] = message
        # determine deferred actions
        reasoning = message.get('reasoning') or '-no-text-'
        content = message.get('content') or '-no-text-'
        tool_calls = message.get('tool_calls')
        if tool_calls:
            for toolcall in tool_calls:
                self.handoff_to_tool(toolcall)
        else:
            self.context['state'] = 'done'
            self.context['final_output'] = content
        return message

    def handoff_to_agent(self, agent, prompt):
        self.add_deferred_action('agent:invoke', dict(agent=agent, prompt=prompt))
        return f"waiting {agent} agent response"

    def handoff_to_human(self, prompt, **kwargs):
        self.add_deferred_action('human:ask', dict(prompt=prompt))
        return "awaiting human response"

    def handoff_to_tool(self, toolcall):
        self.add_deferred_action('tool:call', toolcall)
        return "awaiting tool response"

    def update_action_state(self, action, state):
        # TODO this is currently O(n^2) when combined with iter_responses; make this faster
        for action_item in self.iter_actions(pending=False):
            if action_item['actionid'] == action['actionid']:
                action_item['state'] = state
                action['state'] = state

    def add_deferred_action(self, op, params):
        action = {  # fmt:asis
            'op': op,
            'sessionid': self.sessionid,
            'actionid': uuid4().hex,
            'state': 'pending',
            'params': params,
        }
        self.context['actions'].append(action)
        self.context['state'] = 'awaiting'
        self.save()

    def add_deferred_response(self, action, response):
        self.context['inputs'].append((action, response))
        action['state'] = 'responded'
        self.context['state'] = 'awaiting'
        self.save()

    def handle_deferred_actions(self):
        # handle tool calls and agent handoff
        # -- human input must be provided by someone else
        # TODO this should be called from a runtime task
        for action in self.iter_actions(pending=True):
            op = action.get('op')
            params = action.get('params')
            if op == 'tool:call':
                results, tool_prompts = self._model._call_tools([params], self.sessionid)
                for prompt in tool_prompts:
                    self.add_deferred_response(action, prompt)
            if op == 'agent:invoke':
                subagent = EventAgent(name=params.get('name'), model=self.model)
                message = subagent.invoke(params.get('prompt'))
                self.add_deferred_response(
                    action, {'role': 'user', 'content': f'agent:{subagent.name} response:' + message.get('content')}
                )
            if op == 'human:ask':
                # check sources for input
                pass

    def iter_actions(self, op=None, pending=True):
        for action in self.context['actions']:
            # TODO: is 'pending' the only pending state? e.g. responded is also pending?
            if pending and action['state'] != 'pending':
                continue
            if op and action['op'] not in ensure_list(op):
                continue
            yield action

    def iter_responses(self, op=None, pending=True):
        for action, response in self.context['inputs']:
            if pending and action['state'] not in ['pending', 'responded']:
                continue
            if op and action['op'] not in ensure_list(op):
                continue
            yield action, response


AGENT_SESSIONS = {}


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


class EventAgentBackend(SpecsBackend):
    KIND = 'genai.eventagent'
