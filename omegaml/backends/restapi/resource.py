class GenericResourceMixin:
    def __init__(self, om, raw=False, stream=None, is_async=False, **kwargs):
        super().__init__(**kwargs)
        self.om = om
        self.is_async = is_async
        self.stream = stream
        self.raw = raw
