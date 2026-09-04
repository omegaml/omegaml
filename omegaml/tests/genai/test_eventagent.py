from unittest import TestCase

from omegaml.backends.genai.eventagent import EventAgent
from omegaml.backends.genai.textmodel import TextModel
from omegaml.backends.genai.tools import as_tool_call
from omegaml.backends.genai.replay import ConversationReplay
from omegaml.tests.util import OmegaTestMixin


class EvenAgentTests(OmegaTestMixin, TestCase):
    def setUp(self):
        super().setUp()

    def test_basic_agent_flow(self):
        """test basic response handling"""
        om = self.om
        meta = om.models.put('openai+http://localhost;model=mymodel', 'mymodel', replace=True)
        # prepare an agent
        # -- we fake TextModel.complete() responses, i.e. TextModel.complete() is _not_ called
        agent = EventAgent(model='mymodel')
        replay = ConversationReplay(target=agent)
        replay.add('hello', 'Hello! How can I help you?')
        # check we're getting expected responses
        resp = agent.invoke('hello')
        self.assertEqual(resp['content'], 'Hello! How can I help you?')
        self.assertIsNotNone(agent.sessionid)
        # check conversation id persists across sessions
        sessionid = agent.sessionid
        agent.invoke('hello')
        self.assertEqual(agent.sessionid, sessionid)

    def test_basic_model_flow(self):
        """test basic response handling"""
        om = self.om
        meta = om.models.put('openai+http://localhost;model=mymodel', 'mymodel', replace=True)
        # prepare an agent
        # -- we fake provider responses, i.e. TextModel.complete() is called
        agent = EventAgent(model='mymodel')
        replay = ConversationReplay(target=agent._model)
        replay.add('hello', 'Hello! How can I help you?')
        # check we're getting expected responses
        resp = agent.invoke('hello')
        self.assertEqual(resp['content'], 'Hello! How can I help you?')

    def test_tool_calling(self):
        """test a full cycle with human handoff"""
        om = self.om

        def multiply(a, b):
            return a * b

        om.models.put(multiply, 'tools/multiply', replace=True)
        om.models.put('openai+http://localhost;model=mymodel', 'mymodel', tools=['multiply'], replace=True)

        # prepare agent and tool reply
        # -- we fake provider responses, i.e. TextModel.complete() is called
        agent = EventAgent(model='mymodel')
        replay = ConversationReplay(target=agent._model)
        replay.add('calculate 4 * 5', tool_calls=[as_tool_call(multiply, 4, 5)])
        replay.add('20', 'The final result is 20')
        # check agent state and tool call
        agent.invoke('calculate 4 * 5')
        self.assertEqual(agent.context['state'], 'awaiting')
        actions = agent.context['actions']
        self.assertEqual(len(actions), 1)
        action = actions[0]
        op, params = action['op'], action['params']
        self.assertEqual(op, 'tool:call')
        self.assertIn(params['type'], 'function')
        self.assertIn(params['function']['name'], 'multiply')
        self.assertIn(params['function']['arguments'], '{"args": [4, 5], "kwargs": {}}')
        # handle actions
        agent.handle_deferred_actions()
        actions = agent.context['actions']
        inputs = agent.context['inputs']
        self.assertEqual(len(actions), 1)
        self.assertEqual(agent.context['state'], 'awaiting')
        self.assertEqual(actions[0]['state'], 'responded')  # handoff_to_human() tool should have been called
        action, response = inputs[0]
        self.assertEqual(response['content'], '20')  # handoff_to_human() tool should have been called
        # get agent to process tool response
        agent.invoke('continue')
        self.assertEqual(agent.context['state'], 'done')
        self.assertEqual(agent.context['final_output'], 'The final result is 20')
        actions = agent.context['actions']
        self.assertEqual(actions[0]['state'], 'processed')

    def test_human_handoff(self):
        """test a full cycle with human handoff"""
        om = self.om
        meta = om.models.put('openai+http://localhost;model=mymodel', 'mymodel', replace=True)
        # prepare agent and tool reply
        # -- we fake provider responses, i.e. TextModel.complete() is called
        agent = EventAgent(model='mymodel')
        replay = ConversationReplay(target=agent._model)
        replay.add(
            'calculate 5*2 and ask a human to review',
            tool_calls=[as_tool_call(agent.handoff_to_human, 'is 10 correct?')],
        )
        replay.add('yes, ok', 'thank you, goodbye')
        # check agent state and tool call
        agent.invoke('calculate 5*2 and ask a human to review')
        self.assertEqual(agent.context['state'], 'awaiting')
        actions = agent.context['actions']
        self.assertEqual(len(actions), 1)
        action = actions[0]
        op, params = action['op'], action['params']
        self.assertEqual(op, 'tool:call')
        self.assertEqual(params['type'], 'function')
        self.assertEqual(params['function']['name'], 'handoff_to_human')
        self.assertEqual(params['function']['arguments'], '{"args": ["is 10 correct?"], "kwargs": {}}')
        # handle actions
        agent.handle_deferred_actions()
        self.assertEqual(len(actions), 2)
        self.assertEqual(agent.context['state'], 'awaiting')
        self.assertEqual(actions[0]['state'], 'responded')  # handoff_to_human() tool should have been called
        self.assertEqual(actions[1]['state'], 'pending')  # awaiting human input
        self.assertEqual(actions[1]['op'], 'human:ask')  # this is a human input
        self.assertEqual(actions[1]['params'], dict(prompt='is 10 correct?'))
        # simulate human response
        actions = agent.context['actions']
        agent.add_deferred_response(actions[1], 'yes, ok')  # add a response (this would be by a human)
        # get agent to handle response
        agent.invoke('continue')
        actions = agent.context['actions']
        self.assertEqual(agent.context['state'], 'done')
        self.assertEqual(actions[1]['state'], 'processed')

    def test_saveload(self):
        om = self.om
        meta = om.models.put('openai+http://localhost;model=mymodel', 'mymodel', replace=True)
        # prepare agent and tool reply
        # -- we fake provider responses, i.e. TextModel.complete() is called
        agent = EventAgent(model='mymodel')
        meta = om.models.put(agent, 'agents/myagent')
        reloaded = om.models.get('agents/myagent')
        self.assertEqual(reloaded.context, agent.context)
        self.assertIsInstance(reloaded._model, TextModel)
        self.assertEqual(reloaded._model.base_url, 'http://localhost:80')
        replay = ConversationReplay(target=agent._model)
        replay.add(
            'calculate 5*2 and ask a human to review',
            tool_calls=[as_tool_call(agent.handoff_to_human, 'is 10 correct?')],
        )
        replay.add('yes, ok', 'thank you, goodbye')
        # check agent state and tool call
        agent.invoke('calculate 5*2 and ask a human to review')
        data = agent.tracking.data(run='*')
        # verify we can get sessions back as EventAgent instances
        agent_sessions = agent.sessions()
        self.assertEqual(len(agent_sessions), 1)
        self.assertIsInstance(agent_sessions[-1], EventAgent)
        self.assertIsInstance(agent_sessions[-1]._model, TextModel)
        self.assertEqual(agent_sessions[-1].model, 'mymodel')
        self.assertEqual(agent_sessions[-1].sessionid, agent.sessionid)
        # verify we can get sessions back as dicts of contexts
        agent_sessions = agent.sessions(raw=True)
        self.assertIsInstance(agent_sessions, list)
