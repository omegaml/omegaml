from pathlib import Path
from typing import cast
from uuid import uuid4

from omegaml.backends.genai.modality.multicontent import detect_mime, is_base64
from omegaml.backends.genai.providers import MultimodalProvider
from omegaml.backends.genai.strategy.mixinbase import ConversationModelMixinBase

ALLOWED_EXTENSIONS = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


class AudioMixin(ConversationModelMixinBase):
    def transcribe(self, audio, language=None, response_format=None, data_store=None, as_dict=False, **kwargs):
        """transcribe an audio file

        Args:
            audio (Path|dataset): path to audio file or dataset name in om.datasets
            language (str): optional, language code, defaults to the model's default language
            response_format (str): optional, response format requested from the model provider, defaults to 'json',
              see MultimodalProvider.transcribe() for more options
            data_store (OmegaStore): the om.datasets instance to use if audio is a string, defaults to self.data_store
            as_dict (bool): if True response will be provided as a dict of format

        Returns:
            obj (str|dict): the response in the specified format, defaults to dict for response_format=='json'
        """
        data_store = data_store or self.data_store
        kwargs.update(
            language=language,
            response_format=response_format,
        )
        # see if we can read from the datastore
        is_dataset = isinstance(audio, str) and data_store and audio in data_store
        if is_dataset:
            audio = data_store.get(audio)
        # transcribe
        provider = cast(MultimodalProvider, self.provider)
        self.pipeline(method='prepare', audio=audio, **kwargs)
        resp = provider.transcribe(audio, **kwargs)
        self.pipeline(method='process', audio_response=resp, **kwargs)
        if as_dict:
            resp = {
                'response': resp,
                'is_dataset': is_dataset,
                'format': response_format,
            }
        return resp

    def speech(
        self,
        text,
        voice=None,
        language=None,
        speed=None,
        response_format=None,
        stream=None,
        dataset=None,
        data_store=None,
        as_dict=False,
        **kwargs,
    ):
        """synthesize speech from text

        Args:
            text (str): the text to synthesize
            voice (str): the voice to synthesize, defaults to 'alloy', options are ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
            language (str): optional, language code, defaults to the model's default language
            speed (float): the speed to synthesize in, defaults to 1.0, range in 0.25 to 4.0
            response_format (str): the response format requested from the model provider, see MultimodalProvider.speech()
               for more options
            stream (bool): if True returns an iterator over all chunks in the response, defaults to False
            dataset (str): optional, the name of the output file in om.dataset, mutually exclusive with output_path
            data_store (OmegaStore): optional, the om.datasets store, defaults to self.data_store
            output_path (str|Path): optional, the fully qualified filename for the output file, prefer dataset for efficiency
            as_dict (bool): defaults to False, if True response will be provided as a dict of format {'audio': response, 'is_dataset': True
               if dataset is not None, 'format': response_format}

        Returns:
            obj (dict|str|Metadata|iterable): the response in the specified format, defaults to dict for as_dict=True
        """
        provider = cast(MultimodalProvider, self.provider)
        self.pipeline(method='prepare', text=text, **kwargs)
        if dataset is not None:
            data_store = data_store or self.data_store
            assert data_store is not None, f"need a datastore to save audio file to {dataset}"
            kwargs.update(output_path=Path(data_store.tmppath) / f'{uuid4().hex}.wav')
        kwargs.update(
            response_format=response_format,
            language=language,
            voice=voice,
            speed=speed,
            # stream=stream,
        )
        resp = provider.speech(
            text,
            **kwargs,
        )
        self.pipeline(method='process', speech_response=resp, **kwargs)
        if dataset is not None:
            meta = data_store.put(kwargs['output_path'], dataset, replace=True)
            resp = meta
        print(detect_mime(resp), is_base64(resp))
        if as_dict:
            resp = {
                'response': resp,
                'is_dataset': dataset is not None,
                'format': response_format,
            }
        return resp
