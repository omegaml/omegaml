from uuid import uuid4


class EmbeddingsMixin:
    def embed(self, documents, dimensions=None, raw=False, conversation_id=None, **kwargs):
        dimensions = dimensions or self.kwargs.get('dimensions', 256)
        response = self.provider.embed(documents, dimensions=dimensions, model=self.model, **kwargs)
        conversation_id = conversation_id or uuid4().hex
        self._track_usage(response, conversation_id=conversation_id)
        transformed = (d.get('embedding', d) for d in response.get('data', response))
        return response if raw else list(transformed)
