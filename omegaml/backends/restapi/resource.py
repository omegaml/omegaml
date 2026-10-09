class GenericResourceMixin:
    def __init__(self, om, raw=False, stream=None, streamer=None, is_async=False, **kwargs):
        self.om = om
        self.is_async = is_async
        self.stream = stream
        self.raw = raw
        super().__init__(**kwargs)
