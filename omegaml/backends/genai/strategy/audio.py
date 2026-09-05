from omegaml.backends.genai.providers import MultimodalProvider


class AudioMixin:
    def transcribe(self, audio, **kwargs):
        self.provider: MultimodalProvider
        self.provider.transcribe()
