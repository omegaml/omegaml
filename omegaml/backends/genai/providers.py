import json
import re
from io import FileIO, BytesIO
from pathlib import Path
from typing import Literal, Optional, Union, Generator
from urllib.parse import urljoin

import requests
from openai import OpenAI
from requests._types import SupportsRead

from omegaml.util import ensure_list

filelike = Union[Path, FileIO, BytesIO, SupportsRead]


class Provider:
    URL_REGEX = None

    def __init__(self, api_key, base_url, model=None, tracking=None, **kwargs):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.tracking = tracking

    def embed(self, documents, dimensions=None, **kwargs):
        raise NotImplementedError

    def complete(self, model, messages, stream=False, **kwargs):
        raise NotImplementedError

    @classmethod
    def match_url(cls, url):
        return re.match(cls.URL_REGEX, str(url)) if cls.URL_REGEX else False


class MultimodalProvider(Provider):
    """
    Simple wrapper around an OpenAI‑compatible Text‑to‑Speech endpoint.

    The API key and base URL are supplied when the instance is created,
    so the ``speech`` method only needs the text (and optional overrides).
    """

    def speech(
            self,
            text: str,
            *,
            model: str = "kokoro-v1",
            language: str = "en",
            voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = "alloy",
            response_format: Literal["mp3", "wav", "opus"] = "mp3",
            speed: float = 1.0,
            stream: bool = False,
            output_path: Optional[Union[Path, str]] = None,
    ) -> bytes:
        """
        Generate speech from ``text`` and optionally write it to a file.

        Parameters
        ----------
        text: str
            The text to be spoken.
        model: str, default ``"kokoro-v1"``
            Model identifier; keep the default for OpenAI.
        voice: str, default ``"alloy"``
            Voice to use (one of the OpenAI‑supported voices).
        response_format: str, default ``"mp3"``
            Desired audio container format.
        speed: float, default ``1.0``
            Playback speed (0.25-4.0).
        output_path: Path|str|None, default ``None``
            If provided, the resulting audio bytes are written to this file.

        Returns
        -------
        bytes
            Raw audio data returned by the API.

        Raises
        ------
        requests.HTTPError
            If the HTTP request fails.
        """
        endpoint = f"{self.base_url}/audio/speech"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": response_format,
            "speed": speed,
            "stream": stream,
            "language": language
        }

        resp = requests.post(endpoint, headers=headers, data=json.dumps(payload))
        resp.raise_for_status()  # propagate HTTP errors

        audio_bytes = resp.content

        if output_path is not None:
            Path(output_path).write_bytes(audio_bytes)
            return output_path

        return audio_bytes if not stream else resp

    def transcribe(
            self,
            audio_path: str | Path | bytes | filelike,
            *,
            model: str = "Whisper-Tiny",
            language: Optional[str] = None,
            response_format: Literal["json", "text", "srt", "verbose_json", "vtt"] = "text",
            temperature: float = 0.0,
    ) -> Union[str, dict]:
        """
        Transcribe an audio file with an OpenAI‑compatible Whisper endpoint.

        Parameters
        ----------
        audio_path : str | Path | bytes | FileIO
            Path to the audio file (mp3, mp4, mpeg, mpga, wav, webm).
        model : str, default ``"whisper-1"``
            Whisper model identifier.
        language : str | None, optional
            ISO‑639‑1 language code (e.g., ``"en"``).  If omitted the service
            auto‑detects the language.
        response_format : str, default ``"text"``
            Desired output format – ``"text"`` returns plain transcription,
            ``"json"``/``"verbose_json"`` give structured data,
            ``"srt"``/``"vtt"`` return subtitle formats.
        temperature : float, default ``0.0``
            Sampling temperature; lower values make the output more deterministic.

        Returns
        -------
        str | dict
            The transcription in the requested format.
        """
        url = f"{self.base_url}/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        # Build multipart/form‑data payload
        data = {
            "model": model,
            "language": language if language else "",
            "response_format": response_format,
            "temperature": str(temperature),
        }

        if isinstance(audio_path, (str, Path)) and Path(audio_path).exists():
            fobj = Path(audio_path).open('rb')
            files = {
                "file": (Path(audio_path).name, fobj, "application/octet-stream")
            }
        elif hasattr(audio_path, 'read'):
            name = getattr(audio_path, 'name', 'audio.wav')
            audio_path: BytesIO
            files = {
                "file": (name, audio_path, "application/octet-stream")
            }
        elif isinstance(audio_path, bytes):
            name = 'audio.wav'
            fobj = BytesIO(audio_path)
            files = {
                "file": (name, fobj, "application/octet-stream")
            }
        else:
            raise ValueError(f'cannot process {audio_path} of {type(audio_path)}, ensure valid filelike or list[bytes]')

        response = requests.post(url, headers=headers, data=data, files=files)
        response.raise_for_status()

        if response_format == "text":
            return response.text
        elif response_format in ('json', 'verbose_json'):
            return response.json()
        elif response_format in ('srt', 'vtt'):
            return response.text
        else:
            return response

    def generate_image(
            self,
            prompt: str,
            *,
            model: str = "SD-Turbo",  # common OpenAI model name; adjust for other providers
            n: int = 1,
            size: Literal["256x256", "512x512", "1024x1024"] = "256x256",
            steps: int = 4,
            response_format: Literal["url", "b64_json"] = "b64_json",
            style: Optional[Literal["vivid", "natural"]] = None,
            quality: Optional[Literal["standard", "hd"]] = None,
            raw: bool = False,
    ) -> Union[list[str], list[dict]]:
        """
        Create images from a text prompt via the ``/v1/images/generations`` endpoint.

        Parameters
        ----------
        prompt : str
            Description of the image to generate.
        model : str, default ``"dall-e-3"``
            Image generation model identifier.
        n : int, default ``1``
            Number of images to generate (provider‑specific limits may apply).
        steps: int, default 4, the number of steps to take
        size : str, default ``"1024x1024"``
            Desired pixel dimensions.
        response_format : str, default ``"url"``
            ``"url"`` returns a hosted image URL; ``"b64_json"`` returns the
            image data base‑64‑encoded inside JSON.
        style : str | None, optional
            ``"vivid"`` or ``"natural"`` (OpenAI only); ignored by providers that
            don’t support it.
        quality : str | None, optional
            ``"standard"`` or ``"hd"`` (available on some providers).
        raw : bool, optional, default False, if True returns the raw unparsed data

        Returns
        -------
        list[str] | list[dict]
            If ``response_format="url"``, a list of URLs (``list[str]``);
            if ``response_format="b64_json"``, a list of dictionaries containing
            ``{'b64_json': '<base64 data>'}``.
        """
        url = f"{self.base_url}/images/generations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict = {
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": size,
            "steps": steps,
            "response_format": response_format,
        }

        # Optional parameters – only include them when the caller supplies a value
        if style:
            payload["style"] = style
        if quality:
            payload["quality"] = quality

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        # The response schema is ``{"data": [{"url": ...}, ...]}`` for url format
        # or ``{"data": [{"b64_json": ...}, ...]}`` for base‑64 format.
        return data if raw else [item.get("url") if response_format == "url" else item.get('b64_json') for item in
                                 data.get("data", [])]

    def completions(
            self,
            messages: list[dict],
            *,
            model: str = "gpt-oss-20b-NPU",  # default – change per provider
            temperature: float = 0.7,
            max_tokens: int | None = None,
            top_p: float = 1.0,
            n: int = 1,
            stream: bool = False,
            stop: str | list[str] | None = None,
            response_format: Literal["json_object", "text"] = "text",
    ) -> dict | Generator[dict, None, None]:
        """
        Call the ``/v1/chat/completions`` endpoint (OpenAI‑compatible).

        Parameters
        ----------
        messages : list[dict]
            Conversation history, e.g.
            ``[{"role": "system", "content": "You are helpful."},
               {"role": "user", "content": "Hello"}]``.
        model : str, default ``"gpt-4o-mini"``
            Model identifier.
        temperature : float, default ``0.7``
            Sampling temperature.
        max_tokens : int | None, optional
            Upper bound on generated tokens.
        top_p : float, default ``1.0``
            Nucleus sampling cutoff.
        stream : bool, default ``False``
            If ``True``, returns a generator yielding partial response objects
            (SSE‑style streaming).  If ``False``, returns the full JSON response.
        stop : str | list[str] | None, optional
            Stop sequences.
        response_format : str, default ``"text"``
            ``"text"`` for plain completion, ``"json_object"`` for structured output.

        Returns
        -------
        dict | Generator[dict, None, None]
            - When ``stream=False`` → the full JSON response as a ``dict``.
            - When ``stream=True``  → a generator that yields each SSE ``data``
              fragment decoded from base‑64 (as a ``dict``) until a ``[DONE]``
              event is received.
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict = {
            "model": model,
            "messages": messages,
            # "temperature": temperature,
            # "top_p": top_p,
            "stream": stream,
        }
        if stop is not None:
            payload["stop"] = stop
        if max_tokens is not None:
            payload["max_completion_tokens"] = n
        # payload["modalities"] = ["text", "audio"]

        # -------------------------------------------------
        # Non‑streaming request
        # -------------------------------------------------
        if not stream:
            resp = requests.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()

        # -------------------------------------------------
        # Streaming request – yield each chunk as a dict
        # -------------------------------------------------
        resp = requests.post(
            url,
            headers={**headers, "Accept": "text/event-stream"},
            json=payload,
            stream=True,
        )
        resp.raise_for_status()

        def _sse_generator():
            """
            Parse the Server‑Sent Events stream.  Each ``data:`` line contains a
            JSON fragment (not base‑64 because OpenAI returns raw JSON in the
            stream).  The generator yields the parsed dicts.
            """
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data:"):
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    yield json.loads(data)

        return _sse_generator()


class OpenAIProvider(MultimodalProvider):
    URL_REGEX = r'https?://(api\.openai\.com|localhost)(:\d+)?/.*'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model = self.model

    def embed(self, documents, dimensions=None, model=None, **kwargs):
        documents = ensure_list(documents)
        response = self.client.embeddings.create(
            model=model or self.model, input=documents, dimensions=dimensions, encoding_format="float"
        )
        return response.to_dict()

    def complete(self, messages, stream=False, model=None, **kwargs):
        if stream:
            # https://community.openai.com/t/usage-stats-now-available-when-using-streaming-with-the-chat-completions-api-or-completions-api/738156
            kwargs.setdefault('stream_options', {"include_usage": True})
        response = self.client.chat.completions.create(
            model=model or self.model, messages=messages, stream=stream, **kwargs
        )
        return response.to_dict() if not stream else (chunk.to_dict() for chunk in response)


class JinaEmbeddingsProvider(Provider):
    URL_REGEX = r'https?://(api\.jina\.ai)(:\d+)?/.*'

    def embed(self, documents, dimensions=None, model=None, **kwargs):
        """Embed documents using Jina AI's embedding service.

        Args:
            documents (list): List of documents to embed.
            dimensions (int): Number of dimensions to embed to.
            model (str): Model name to use for embedding.

        Returns:
            list: List of embeddings as list[list[float, ...]].
        """
        # see https://jina.ai/embeddings
        documents = ensure_list(documents)
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'}
        url = urljoin(self.base_url, 'embeddings')
        resp = requests.post(
            url, headers=headers, json={'model': self.model, 'input': [{'text': doc} for doc in documents]}
        )
        assert resp.status_code == 200, f'Error {resp.status_code} calling {url}: {resp.text}'
        response = resp.json()
        return response


class AnythingLLMProvider(Provider):
    URL_REGEX = r'https?://(api\.anythingllm\.com|localhost:(3001)+|anythingllm\.com)/.*'

    def embed(self, documents, dimensions=None, **kwargs):
        """Embed documents

        Args:
            documents (list): list of documents to embed
            dimensions (int): number of dimensions to embed to

        Returns:
            list: list of embeddings as list[list[float, ...]]
        """
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'}
        url = urljoin(self.base_url, 'embeddings')
        documents = ensure_list(documents)
        resp = requests.post(url, headers=headers, json={'inputs': documents, 'model': self.model})
        assert resp.status_code == 200, f'Error {resp.status_code} calling {url}: {resp.text}'
        response = resp.json()
        return response

    def complete(self, messages, stream=False, **kwargs):
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'}
        url = f'{self.base_url}/chat/completions'
        resp = requests.post(url, headers=headers, json={'messages': messages, 'model': self.model, 'stream': stream})
        return resp.json()


class OllamaProvider(Provider):
    URL_REGEX = r'https?://(api\.ollama\.com|localhost)(:\d+)?/.*'

    def embed(self, documents, dimensions=None, **kwargs):
        """Embed documents using Ollama's embedding service.

        Args:
            documents (list): List of documents to embed.
            dimensions (int): Number of dimensions to embed to.

        Returns:
            list: List of embeddings as list[list[float, ...]].
        """
        # see https://ollama.com/docs/api/embeddings
        documents = ensure_list(documents)
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'}
        url = urljoin(self.base_url, 'embeddings')
        resp = requests.post(url, headers=headers, json={'model': self.model, 'input': documents})
        assert resp.status_code == 200, f'Error {resp.status_code} calling {url}: {resp.text}'
        response = resp.json()
        return response


PROVIDERS = {
    'openai': OpenAIProvider,
    'anythingllm': AnythingLLMProvider,
    'jina': JinaEmbeddingsProvider,
    'default': OpenAIProvider,
}
