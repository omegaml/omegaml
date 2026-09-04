import warnings

from omegaml.backends.genai.models.conversation import ConversationModel, ConversationModelBackend


class TextModel(ConversationModel):
    """
       .. deprecated:: NEXT
          Use ConversationModel instead. TextModel will be removed in the next release.
       """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        warnings.warn(
            "TextModel is deprecated. Use ConversationModel instead.", DeprecationWarning,
            stacklevel=2)


class TextModelBackend(ConversationModelBackend):
    KIND = 'genai.text'

    def __repr__(self):
        return f'TextModel(base_url={self.base_url}, model={self.model})'
