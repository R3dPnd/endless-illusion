import re
from urllib.parse import urlsplit


def normalize_url(url):
    """
    Canonical key for a program URL so repeat sightings group together:
    lowercase host without "www.", path without trailing slash, no scheme or query.
    """
    raw = str(url).strip()
    with_scheme = raw if re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.I) else f"https://{raw}"
    try:
        parsed = urlsplit(with_scheme)
        host = parsed.hostname
    except ValueError:
        host = None
    if not host:
        return re.sub(r"/+$", "", raw.lower())
    host = re.sub(r"^www\.", "", host.lower())
    return host + re.sub(r"/+$", "", parsed.path.lower())
