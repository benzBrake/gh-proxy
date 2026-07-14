import unittest
from unittest.mock import patch

from app.security import is_secure_github_api_url, sanitize_request_headers


class SanitizeRequestHeadersTest(unittest.TestCase):
    def test_removes_credentials_and_untrusted_headers(self):
        headers = sanitize_request_headers({
            'Authorization': 'Bearer secret',
            'Cookie': 'session=secret',
            'Proxy-Authorization': 'Basic secret',
            'X-Forwarded-For': '127.0.0.1',
            'Host': 'proxy.example',
        }, 'https://github.com/owner/repo/archive/main.zip')

        self.assertEqual(headers, {})

    def test_keeps_authorization_only_for_secure_github_api(self):
        headers = sanitize_request_headers(
            {'Authorization': 'token secret'},
            'https://api.github.com/repos/owner/repo/releases',
        )

        self.assertEqual(headers, {'Authorization': 'token secret'})

    def test_removes_authorization_from_unsafe_api_targets(self):
        targets = (
            'http://api.github.com/repos/owner/repo/releases',
            'https://api.github.com:8443/repos/owner/repo/releases',
            'https://codeload.github.com/owner/repo/zip/main',
            'https://api.github.com.example.test/repos/owner/repo',
            'not a url',
        )

        for target in targets:
            with self.subTest(target=target):
                self.assertEqual(
                    sanitize_request_headers(
                        {'Authorization': 'Bearer secret'}, target),
                    {},
                )

    def test_secure_github_api_accepts_default_https_port(self):
        self.assertTrue(is_secure_github_api_url('https://api.github.com/rate_limit'))
        self.assertTrue(is_secure_github_api_url('https://api.github.com:443/rate_limit'))

    def test_keeps_headers_needed_for_downloads_and_api_requests(self):
        headers = sanitize_request_headers({
            'Range': 'bytes=100-200',
            'If-None-Match': 'etag',
            'Content-Type': 'application/json',
            'X-GitHub-Api-Version': '2022-11-28',
        }, 'https://github.com/owner/repo/archive/main.zip')

        self.assertEqual(headers, {
            'Range': 'bytes=100-200',
            'If-None-Match': 'etag',
            'Content-Type': 'application/json',
            'X-GitHub-Api-Version': '2022-11-28',
        })


class CustomFrontendTest(unittest.TestCase):
    def test_cached_custom_frontend_is_served(self):
        from app import main

        client = main.app.test_client()
        with patch.object(main, 'index_html', '<h1>Custom frontend</h1>'), \
                patch.object(main, 'icon_r', b'icon'):
            response = client.get('/')
            favicon = client.get('/favicon.ico')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Custom frontend', response.data)
        self.assertEqual(favicon.status_code, 200)
        self.assertEqual(favicon.data, b'icon')


if __name__ == '__main__':
    unittest.main()
