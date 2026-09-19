import re
from typing import Any, BinaryIO

from omegaml.backends.genai.modality.image import jpg_to_base64
from omegaml.backends.genai.modality.sound import wav_to_base64

# ----------------------------------------------------------------------
# Helper: map a MIME type to the OpenAI content “type” and the payload shape
# ----------------------------------------------------------------------
_MIME_TO_OPENAI = {
    # ----- Images -------------------------------------------------------
    "image": ("image_url", lambda b64, mime: {"url": f"data:{mime};base64,{b64}"}),
    "image/jpeg": ("image_url", lambda b64, mime: {"url": f"data:{mime};base64,{b64}"}),
    "image/jpg": ("image_url", lambda b64, mime: {"url": f"data:{mime};base64,{b64}"}),
    "image/gif": ("image_url", lambda b64, mime: {"url": f"data:{mime};base64,{b64}"}),
    "image/webp": ("image_url", lambda b64, mime: {"url": f"data:{mime};base64,{b64}"}),
    # ----- Audio --------------------------------------------------------
    "audio/wav": ("input_audio", lambda b64, mime: {"data": b64, "format": "wav"}),
    "audio/x-wav": ("input_audio", lambda b64, mime: {"data": b64, "format": "wav"}),
    "audio/mp3": ("input_audio", lambda b64, mime: {"data": b64, "format": "mp3"}),
    "audio/mpeg": ("input_audio", lambda b64, mime: {"data": b64, "format": "mp3"}),
    "audio/ogg": ("input_audio", lambda b64, mime: {"data": b64, "format": "ogg"}),
    # ----- Fall‑back (plain text) ----------------------------------------
    "application/pdf": ("text", lambda b64, mime: b64),
    "application/zip": ("text", lambda b64, mime: b64),
    "application/octet-stream": ("text", lambda b64, mime: b64),
}


def detect_mime(data: bytes) -> str:
    return guess_type(data)


def binary_to_openai_content(
    file_obj: BinaryIO, *, as_uri: bool = False, audio_kwargs: dict, image_kwargs: dict
) -> dict[str, Any]:
    """
    Read an arbitrary binary *file‑like* object and build an OpenAI‑compatible
    ``messages`` element.

    The function automatically chooses the correct ``type`` for the OpenAI
    Chat Completions API:

    * **image_url** – for PNG, JPEG, GIF, WebP images (returns a data‑URI).
    * **input_audio** – for common audio formats (WAV, MP3, OGG).  The payload
      follows the shape required by the Audio input API
      (``{\"speech\": <base64>, \"format\": <ext>}``).
    * **text** – everything else – the raw Base64 string is placed in the
      ``text`` field.

    Parameters
    ----------
    file_obj : BinaryIO
        Any object exposing ``read()`` and returning ``bytes``.
    as_uri : bool, default ``False``
        When ``True`` the function always returns a data‑URI (useful for
        embedding in HTML).  For non‑image/audio types the flag has no effect
        because the OpenAI API expects plain Base64 text.
    audio_kwargs : dict, optional, kwargs passed on to wav_to_base64()
    image_kwargs : dict, optional, kwargs passed on to jpg_to_base64(), defaults to
        dict(max_weight=256, max_height=256)

    Returns
    -------
    dict
        A message dict that can be supplied directly to
        ``client.chat.completions.create(messages=[msg])``.
    """
    audio_kwargs = audio_kwargs or {}
    image_kwargs = image_kwargs or {
        'max_width': 256,
        'max_height': 256,
    }
    # Detect MIME from the content
    mime = detect_mime(file_obj.read(1024))
    file_obj.seek(0)

    # Choose OpenAI content type
    openai_type, formatter = _MIME_TO_OPENAI.get(
        mime,
        ("text", lambda b, m: b),  # default → plain text
    )

    # Build the ``content`` entry based on the chosen type
    if openai_type == "image_url":
        b64 = jpg_to_base64(file_obj.read(), as_uri=as_uri, **image_kwargs)
        payload = formatter(b64, mime)  # returns {"image_url": ..., "format": ...}
        content_item = {"type": "image_url", "image_url": payload}
    elif openai_type == "input_audio":
        b64 = wav_to_base64(file_obj.read(), as_uri=as_uri, **audio_kwargs)
        payload = formatter(b64, mime)  # returns {"data": ..., "format": ...}
        content_item = {"type": "input_audio", "input_audio": payload}
    else:
        raise ValueError(f'cannot use data of type {mime=}')

    # Wrap into the full message structure expected by the API.
    return {"role": "user", "content": [content_item]}


import mimetypes
import os


def guess_type(input_val):
    # python only mime test to avoid os-specific library dependencies
    # -- see https://en.wikipedia.org/wiki/List_of_file_signatures
    signatures = {
        b'\xff\xd8\xff': 'image/jpeg',
        b'\x89PNG\r\n\x1a\n': 'image/png',
        b'GIF87a': 'image/gif',
        b'GIF89a': 'image/gif',
        b'%PDF': 'application/pdf',
        b'PK\x03\x04': 'application/zip',  # zip, docx, xlsx, jar, etc.
        b'\x1f\x8b': 'application/gzip',
        b'BM': 'image/bmp',
        b'II\x2a\x00': 'image/tiff',
        b'MM\x00\x2a': 'image/tiff',
        b'RIFF': 'audio/wav',  # followed by WAVE
        b'ID3': 'audio/mpeg',  # MP3
        b'\xff\xfb': 'audio/mpeg',  # MP3 (MPEG ADTS)
        b'\xff\xfa': 'audio/mpeg',  # MP3 (MPEG ADTS)
    }

    # 1. Normalize input to bytes
    # If it's a path to a file, read the header.
    # If it's already bytes/string, use it directly.
    if isinstance(input_val, str) and os.path.exists(input_val):
        with open(input_val, 'rb') as f:
            f.seek(0)
            data = f.read(8)
    elif isinstance(input_val, bytes):
        data = input_val[:8]
    elif isinstance(input_val, str):
        data = input_val.encode('utf-8')[:8]
    else:
        data = b''

    # 2. The Single Logic Test: Signature check
    for sig, mime in signatures.items():
        if data.startswith(sig):
            return mime

    # 3. Final fallback to extension (only possible if input was a string)
    if isinstance(input_val, str):
        mime_type, _ = mimetypes.guess_type(input_val)
        if mime_type:
            return mime_type

    return 'application/octet-stream'


def is_base64(s):
    # 1. Must be a string
    # 2. Length must be a multiple of 4
    # 3. Only A-Z, a-z, 0-9, +, / allowed
    # 4. Max 2 '=' allowed only at the end
    if not isinstance(s, str) or len(s) % 4 != 0:
        return False
    return bool(re.fullmatch(r'[A-Za-z0-9+/]*={0,2}', s))


# ----------------------------------------------------------------------
# Example usage ---------------------------------------------------------
# ----------------------------------------------------------------------
def example():
    # Image → automatically becomes an ``image_url`` entry
    with open("duck.jpg", "rb") as fp:
        img_msg = binary_to_openai_content(fp)
    print(img_msg)

    # Audio → automatically becomes an ``input_audio`` entry
    with open("greeting.wav", "rb") as fp:
        audio_msg = binary_to_openai_content(fp)
    print(audio_msg)

    # PDF (fallback to text)
    with open("report.pdf", "rb") as fp:
        pdf_msg = binary_to_openai_content(fp, as_uri=True)
    print(pdf_msg)

    with open("greeting.wav", "rb") as fp:
        audio_msg = binary_to_openai_content(fp)
        print(audio_msg)

    # --- Examples ---
    # As a file path
    # print(guess_type("test.png"))

    # As a raw byte string (header)
    print(guess_type(b'\x89PNG\r\n\x1a\n'))  # image/png

    # As a plain string (fallback to extension)
    print(guess_type("document.pdf"))  # application/pdf
