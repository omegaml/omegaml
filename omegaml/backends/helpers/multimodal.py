from omegaml.backends.virtualobj import virtualobj


@virtualobj
def helper(*args, method=None, backend=None, **kwargs):
    import inspect

    import omegaml as om
    from omegaml.backends.genai.providers import MultimodalProvider
    from omegaml.backends.genai.strategy.audio import AudioMixin

    def override(m, cls, fixup=lambda c, *args, **kwargs: c(*args, **kwargs)):
        _m = getattr(cls, f'_orig_{m}', getattr(cls, m))
        _m_override = lambda *args, raw=None, **kwargs: fixup(_m, *args, **kwargs)
        setattr(cls, m, _m_override)
        setattr(cls, f'_orig_{m}', _m) if not hasattr(cls, f'_orig_{m}') else None

    def transcribe_fix(c, self, *args, **kwargs):
        # overrides MultimodalProvider.transcribe()
        # caller is ConversationModel
        # issues resolved:
        # -- fix the REST API provides the payload in args[0][0] as a dict
        # -- fix the model is the REST API model, instead of ConversationModel.model
        if isinstance(args[0], list) and isinstance(args[0][0], dict):
            kwargs.update(args[0][0])
            args = [kwargs.pop('file')]
            kwargs.pop('audio', None)
            kwargs.pop('model', None)
            frame = inspect.currentframe()
            caller_locals = frame.f_back.f_back.f_locals
            caller_self = caller_locals.get("self")
            kwargs['model'] = getattr(caller_self, 'model', None)
            om.logger.info(kwargs)
        return c(self, *args, **kwargs)

    def speech_fix(c, self, *args, **kwargs):
        # # overrides MultimodalProvider.transcribe()
        # caller is ConversationModel
        # issues resolved:
        # -- fix the REST API provides the payload in args[0][0] as a dict
        # -- fix the model is the REST API model, instead of ConversationModel.model
        if isinstance(args[0], list) and isinstance(args[0][0], dict):
            frame = inspect.currentframe()
            caller_locals = frame.f_back.f_back.f_locals
            caller_self = caller_locals.get("self")
            kwargs.update(args[0][0])
            args = [kwargs.pop('text')]
            kwargs.pop('model', None)
            kwargs.pop('dataset', None)
            kwargs['model'] = getattr(caller_self, 'model', None)
            om.logger.info(kwargs)
        return c(self, *args, **kwargs)

    def audio_speech_fix(c, self, *args, **kwargs):
        # overrides AudioMixin.speech()
        # caller is ConversationModel
        # issues resolved:
        # -- fix the REST API requires dataset=None to avoid storing in om.datasets
        #    (causes Metadata serialization in kombu, which fails)
        if isinstance(args[0], list) and isinstance(args[0][0], dict):
            kwargs.pop('dataset', None)
        return c(self, *args, **kwargs)

    override('transcribe', MultimodalProvider, fixup=transcribe_fix)
    override('speech', MultimodalProvider, fixup=speech_fix)
    override('speech', AudioMixin, fixup=audio_speech_fix)


def install():
    import omegaml as om

    # as_source=True ensures this helper works across all Python versions
    om.models.put(helper, ".helpers/multimodal", supports='kind:experiment.tracker', replace=True, as_source=True)
