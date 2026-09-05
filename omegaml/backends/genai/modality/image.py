import base64
from io import BytesIO
from pathlib import Path

from PIL import Image


def jpg_to_base64(
        src_path: str | Path | bytes,
        *,
        max_width: int | None = None,
        max_height: int | None = None,
        quality: int = 85,
        as_uri: bool = False,
) -> str:
    """
    Convert a JPEG to a Base64 string, optionally resizing it first.

    Parameters
    ----------
    src_path : str or Path
        Path to the original ``.jpg`` file.
    max_width : int, optional
        Maximum width in pixels (down‑scale only if larger).
    max_height : int, optional
        Maximum height in pixels (down‑scale only if larger).
    quality : int, default 85
        JPEG quality for the in‑memory save.
    as_uri : bool, default False
        If True, return a full data‑URI (``data:image/jpeg;base64,…``);
        otherwise return the bare Base64 string.

    Returns
    -------
    str
        Base64‑encoded JPEG, or a data‑URI when ``as_uri=True``.
    """
    if isinstance(src_path, (str, Path)):
        src_path = Path(src_path)
    else:
        src_path = BytesIO(src_path)

    # Open the JPEG
    with Image.open(src_path) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")

        # ------- Resize while keeping aspect ratio ---------
        if max_width or max_height:
            orig_w, orig_h = img.size
            target_w, target_h = orig_w, orig_h

            if max_width and orig_w > max_width:
                target_w = max_width
                target_h = int(orig_h * (max_width / orig_w))

            if max_height and target_h > max_height:
                target_h = max_height
                target_w = int(target_w * (max_height / target_h))

            if (target_w, target_h) != (orig_w, orig_h):
                img = img.resize((target_w, target_h), Image.LANCZOS)

        # ------- Encode to Base64 -------------------------
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)

        b64_bytes = base64.b64encode(buffer.read())
        b64_str = b64_bytes.decode("utf-8")

        # Return either raw Base64 or a full data‑URI
        if as_uri:
            return f"data:image/jpeg;base64,{b64_str}"
        return b64_str


def example():
    # -------------------------- Example calls ---------------------------
    # 1️⃣ Just encode, no resize
    print(jpg_to_base64("duck.jpg"))

    # 2️⃣ Resize to fit within 800 px (either dimension) and get a data‑URI
    print(jpg_to_base64("duck.jpg", max_width=800, max_height=800, as_uri=True))

    # 3️⃣ Fit inside 400×300 px, return plain Base64
    print(jpg_to_base64("duck.jpg", max_width=400, max_height=300))

    # 4️⃣ Full data‑URI with default sizing
    print(jpg_to_base64("duck.jpg", as_uri=True))
