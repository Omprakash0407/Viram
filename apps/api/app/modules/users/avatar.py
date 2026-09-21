"""Avatar handling: validate + store a URL, never binary blobs in `users`.

Storage model (MVP): the browser downscales the chosen image to a small square
data URL client-side (≤ ~40 KB), so the platform needs no object store and the
API stores a self-contained string. Only http(s) URLs and same-size data URLs
are accepted — anything else is rejected before it reaches the database.
"""

from __future__ import annotations

import re

from app.core.exceptions import ValidationError

# ~48 KB of base64 ≈ 36 KB binary — plenty for a 96×96 avatar.
MAX_DATA_URL_CHARS = 64_000
_DATA_URL_RE = re.compile(r"^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=\s]+$")
_HTTP_URL_RE = re.compile(r"^https://\S+$", re.IGNORECASE)


def validate_avatar_url(url: str | None) -> str | None:
    """Accept https URLs or an image data URL; reject everything else."""
    if url is None:
        return None
    url = url.strip()
    if not url:
        return None
    if _DATA_URL_RE.match(url):
        if len(url) > MAX_DATA_URL_CHARS:
            raise ValidationError(
                "Avatar image is too large — pick a smaller photo (it is "
                "resized automatically in the app)."
            )
        return url
    if _HTTP_URL_RE.match(url):
        # https only: avatars are rendered on every page; no mixed content.
        return url
    raise ValidationError(
        "Avatar must be an https image URL or an uploaded picture."
    )
