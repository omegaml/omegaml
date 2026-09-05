from typing import BinaryIO, Dict, Any

import magic  # pip install python‑magic

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


def _detect_mime(data: bytes) -> str:
    """
    Use libmagic (python‑magic) to infer a MIME type from the raw bytes.
    """
    # ``magic.from_buffer`` returns a string like ``image/png``.
    return magic.from_buffer(data, mime=True)


def binary_to_openai_content(
        file_obj: BinaryIO,
        *,
        as_uri: bool = False,
        audio_kwargs: dict,
        image_kwargs: dict
) -> Dict[str, Any]:
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
    mime = _detect_mime(file_obj.read(1024))
    file_obj.seek(0)

    # Choose OpenAI content type
    openai_type, formatter = _MIME_TO_OPENAI.get(
        mime, ("text", lambda b, m: b)  # default → plain text
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
