from __future__ import annotations

import re
from urllib.parse import urlparse


def site_slug(url: str) -> str:
    parsed = urlparse(url)
    base = parsed.netloc or parsed.path or "site"
    base = base.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return slug or "site"
