from omegaml.backends.genai.providers import PROVIDERS
from omegaml.backends.genai.strategy.mixinbase import ConversationModelMixinBase


class ProviderMixin(ConversationModelMixinBase):
    """dynamically load the model provider

    Instance variables:
        self._provider(str|Provider): the provider name or instance of the provider.

    How this works:
        this works by using the self.provider variable to set a provider name or Provider instance.
        If the provider is a string
    """

    def resolve_provider(self, provider):
        provider = PROVIDERS[provider](
            api_key=self.api_key, base_url=self.base_url, model=self.model, tracking=self.tracking
        )
        return provider

    @property
    def provider(self):
        if isinstance(self._provider, str):
            self._provider = self.resolve_provider(self._provider)
        return self._provider

    @provider.setter
    def provider(self, name_or_instance):
        self._provider = name_or_instance
