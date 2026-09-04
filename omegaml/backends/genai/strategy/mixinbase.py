from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omegaml.backends.genai.models import ConversationModel

    ConversationModelMixinBase = ConversationModel
else:
    ConversationModelMixinBase = object
