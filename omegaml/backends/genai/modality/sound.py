import base64
from pathlib import Path


def wav_to_base64(
        src_path: str | Path | bytes,
        *,
        as_uri: bool = False,
) -> str:
    """
    Read a WAV file and return its Base64 representation.

    Parameters
    ----------
    src_path : str or Path
        Path to the ``.wav`` file.
    as_uri : bool, default False
        If True, return a full data‑URI (``data:audio/wav;base64,…``);
        otherwise return just the Base64 string.

    Returns
    -------
    str
        Base64‑encoded audio, or a data‑URI when ``as_uri=True``.
    """
    if isinstance(src_path, (Path, str)):
        src_path = Path(src_path)

        # Read the raw bytes of the WAV file
        with src_path.open("rb") as f:
            wav_bytes = f.read()
    else:
        wav_bytes = bytes(src_path)

    # Encode to Base64
    b64_bytes = base64.b64encode(wav_bytes)
    b64_str = b64_bytes.decode("utf-8")

    # Return either raw Base64 or a data‑URI
    if as_uri:
        return f"data:audio/wav;base64,{b64_str}"
    return b64_str


def example():
    # --------------------------- Example usage ---------------------------
    # 1️⃣ Simple Base64 string
    b64 = wav_to_base64("greeting.wav")
    print(b64)

    # 2️⃣ Data‑URI ready for embedding in HTML/audio tags
    uri = wav_to_base64("greeting.wav", as_uri=True)
    print(uri)  # e.g. <audio src="data:audio/wav;base64,...."></audio>
