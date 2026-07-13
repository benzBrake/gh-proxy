from unittest.mock import Mock

import pytest

from app import main


class RawResponse:
    def __init__(self, chunks):
        self.raw = Mock()
        self.raw.stream.return_value = iter(chunks)
        self._content_consumed = False
        self._content = False
        self.close = Mock()


def test_iter_limited_content_closes_response_after_success():
    response = RawResponse([b'ab', b'cd'])

    assert list(main.iter_limited_content(response, 4, chunk_size=2)) == [b'ab', b'cd']
    response.close.assert_called_once_with()


def test_iter_limited_content_aborts_and_closes_when_actual_bytes_exceed_limit():
    response = RawResponse([b'ab', b'cdef'])
    stream = main.iter_limited_content(response, 4, chunk_size=4)

    assert next(stream) == b'ab'
    with pytest.raises(main.ResponseSizeLimitExceeded):
        next(stream)
    response.close.assert_called_once_with()


def test_download_rules_uses_configured_timeout(monkeypatch, tmp_path):
    response = Mock(text='owner/repo\n')
    monkeypatch.setitem(main.DEFAULT_RULES, 'whitelist', str(tmp_path / 'rules'))
    get = Mock(return_value=response)
    monkeypatch.setattr(main.requests, 'get', get)

    assert main.download_rules_list('UNSET_RULE_URL', 'whitelist', 'https://example.test/rules') == [
        ('owner', 'repo')
    ]
    get.assert_called_once_with('https://example.test/rules', timeout=main.REQUEST_TIMEOUT)


def test_regular_proxy_request_uses_configured_timeout(monkeypatch):
    upstream = Mock(headers={}, status_code=200)
    monkeypatch.setattr(main.requests, 'request', Mock(return_value=upstream))

    with main.app.test_request_context('/https://github.com/owner/repo/archive/main.zip'):
        response = main.proxy('https://github.com/owner/repo/archive/main.zip')

    assert response.status_code == 200
    assert main.requests.request.call_args.kwargs['timeout'] == main.REQUEST_TIMEOUT
    response.close()
