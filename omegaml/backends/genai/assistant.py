from omegaml.backends.genai import ConversationModelBackendMixin
from omegaml.backends.genai.models import ConversationModel
from omegaml.backends.specsobj import SpecsBackend, SpecsMixin
from omegaml.client.util import subdict_except


class AssistantBackend(ConversationModelBackendMixin, SpecsBackend):
    KIND = 'genai.assistant'


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
            tracking=self.tracking,
            **subdict_except(self.specs, ['model', 'tracking']),
        )

    def complete(
        self, prompt, messages=None, conversation_id=None, stream=None, use_tools=True, agentic=False, **kwargs
    ):
        self.initialize(load=True)
        return self._model.complete(
            prompt,
            messages=messages,
            conversation_id=conversation_id,
            stream=stream,
            use_tools=use_tools,
            agentic=agentic,
            **kwargs,
        )

    def conversation(self, conversation_id=None, raw=False, **filter):
        self.initialize(load=True)
        return self._model.conversation(conversation_id=conversation_id, raw=raw, **filter)
