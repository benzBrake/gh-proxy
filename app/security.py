from urllib.parse import urlsplit


FORWARDED_REQUEST_HEADERS = frozenset({
    'accept',
    'accept-encoding',
    'accept-language',
    'cache-control',
    'content-length',
    'content-type',
    'if-match',
    'if-modified-since',
    'if-none-match',
    'if-range',
    'if-unmodified-since',
    'pragma',
    'range',
    'user-agent',
    'x-github-api-version',
})


def is_secure_github_api_url(target_url):
    """Return whether a URL is safe to receive a GitHub API credential."""
    if not target_url:
        return False

    try:
        parsed = urlsplit(target_url)
        port = parsed.port
    except ValueError:
        return False

    return (
        parsed.scheme.lower() == 'https'
        and parsed.hostname is not None
        and parsed.hostname.lower() == 'api.github.com'
        and port in (None, 443)
    )


def sanitize_request_headers(headers, target_url=None):
    """Return only request headers that are safe to send to an upstream host."""
    allowed_headers = FORWARDED_REQUEST_HEADERS
    if is_secure_github_api_url(target_url):
        allowed_headers = allowed_headers | {'authorization'}

    return {
        key: value
        for key, value in headers.items()
        if key.lower() in allowed_headers
    }
