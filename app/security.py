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


def sanitize_request_headers(headers):
    """Return only request headers that are safe to send to an upstream host."""
    return {
        key: value
        for key, value in headers.items()
        if key.lower() in FORWARDED_REQUEST_HEADERS
    }
