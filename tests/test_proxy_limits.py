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


def test_proxy_forwards_authorization_to_secure_github_api(monkeypatch):
    upstream = Mock(headers={}, status_code=200)
    github_api_request = Mock(return_value=upstream)
    monkeypatch.setattr(main, 'github_api_request', github_api_request)

    with main.app.test_request_context(
            '/https://api.github.com/repos/owner/repo/releases',
            headers={'Authorization': 'Bearer secret'}):
        response = main.proxy(
            'https://api.github.com/repos/owner/repo/releases')

    assert github_api_request.call_args.kwargs['headers']['Authorization'] == (
        'Bearer secret')
    response.close()


def test_explicit_https_port_uses_github_api_strategy():
    assert main.is_github_api_url(
        'https://api.github.com:443/repos/owner/repo/releases')
    assert not main.is_github_api_url(
        'https://api.github.com:8443/repos/owner/repo/releases')


def test_proxy_strips_authorization_from_redirect_target(monkeypatch):
    upstream = Mock(headers={}, status_code=200)
    request_mock = Mock(return_value=upstream)
    monkeypatch.setattr(main.requests, 'request', request_mock)

    with main.app.test_request_context(
            '/https://api.github.com/repos/owner/repo/zipball/main',
            headers={'Authorization': 'Bearer secret'}):
        response = main.proxy(
            'https://codeload.github.com/owner/repo/legacy.zip/main')

    assert 'Authorization' not in request_mock.call_args.kwargs['headers']
    response.close()


def test_github_api_strategies_preserve_authorization_without_logging_it(
        monkeypatch, caplog):
    rate_limited_primary = Mock(
        headers={'X-RateLimit-Remaining': '0'}, status_code=403)
    rate_limited_secondary = Mock(
        headers={'X-RateLimit-Remaining': '0'}, status_code=403)
    direct_response = Mock(headers={}, status_code=200)
    request_mock = Mock(side_effect=(
        rate_limited_primary,
        rate_limited_secondary,
        direct_response,
    ))
    monkeypatch.setattr(main.requests, 'request', request_mock)
    monkeypatch.setattr(main, 'ENV_API_PROXY', 'http://primary.test:8080')
    monkeypatch.setattr(
        main, 'ENV_API_PROXY_SECONDARY', 'http://secondary.test:8080')
    monkeypatch.setattr(main, 'ENV_API_PROXY_RETRIES', 1)

    response = main.github_api_request(
        method='GET',
        url='https://api.github.com/repos/owner/repo/releases',
        headers={'Authorization': 'Bearer secret'},
        data=b'',
        allow_redirects=False,
    )

    assert response is direct_response
    assert request_mock.call_count == 3
    for call in request_mock.call_args_list:
        assert call.kwargs['headers']['Authorization'] == 'Bearer secret'
    assert request_mock.call_args_list[0].kwargs['proxies'] == {
        'http': 'http://primary.test:8080',
        'https': 'http://primary.test:8080',
    }
    assert request_mock.call_args_list[1].kwargs['proxies'] == {
        'http': 'http://secondary.test:8080',
        'https': 'http://secondary.test:8080',
    }
    assert request_mock.call_args_list[2].kwargs['proxies'] is None
    assert 'Bearer secret' not in caplog.text
