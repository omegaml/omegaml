import uuid

from omegaml.backends.genai import ConversationModelBackendMixin
from omegaml.backends.genai.models import ConversationModel
from omegaml.backends.specsobj import SpecsBackend, SpecsMixin
from omegaml.client.util import subdict_except


class Assistant(SpecsMixin):
    def __init__(
        self, model=None, template=None, documents=None, tools=None, pipeline=None, guardrails=None, strategy=None
    ):
        super().__init__(
            model=model,
            template=template,
            documents=documents,
            tools=tools,
            pipeline=pipeline,
            guardrails=guardrails,
            strategy=strategy,
        )
        self._model: ConversationModel = None

    def load(self):
        import omegaml as om

        self._model = self._model or om.models.get(
            self.model,
            data_store=om.datasets,
            tracking=getattr(self, 'tracking', None),
            **subdict_except(self.specs, ['model', 'tracking']),
        )
        self.conversation_id = getattr(self, 'conversation_id', None)

    def reset(self):
        self.conversation_id = uuid.uuid4().hex
        return self.conversation_id

    def complete(
        self, prompt, messages=None, conversation_id=None, stream=False, use_tools=True, agentic=False, **kwargs
    ):
        self.initialize(load=True)
        self.conversation_id = conversation_id or self.conversation_id or self.reset()
        resp = self._model.complete(
            prompt,
            messages=messages,
            conversation_id=self.conversation_id,
            stream=stream,
            use_tools=use_tools,
            agentic=agentic,
            **kwargs,
        )
        return resp

    def conversation(self, conversation_id=None, raw=False, **filter):
        self.initialize(load=True)
        conversation_id = conversation_id or self.conversation_id
        return self._model.conversation(conversation_id=conversation_id, raw=raw, **filter)

    @property
    def stats(self):
        return self._model.tracking.stats


class AssistantBackend(ConversationModelBackendMixin, SpecsBackend):
    KIND = 'genai.assistant'
    SPECS_CLASS = Assistant
