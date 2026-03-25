# -*- coding: utf-8 -*-
import os
import re
import socket
import sys
import requests
import logging
from flask import Flask, Response, redirect, request
from requests.exceptions import (
    ChunkedEncodingError,
    ContentDecodingError, ConnectionError, StreamConsumedError)
from requests.utils import (
    stream_decode_response_unicode, iter_slices, CaseInsensitiveDict)
from urllib3.exceptions import (
    DecodeError, ReadTimeoutError, ProtocolError)
from urllib.parse import quote, urlparse

# Path management
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES_DIR = os.path.join(BASE_DIR, 'resources')

DEFAULT_RULES = {
    'whitelist': os.path.join(RESOURCES_DIR, 'whitelist_rules'),
    'blacklist': os.path.join(RESOURCES_DIR, 'blacklist_rules'),
    'passlist': os.path.join(RESOURCES_DIR, 'passlist_rules'),
}

# Backward compatibility: fallback to root directory
LEGACY_RULES = {
    'whitelist': 'whitelist',
    'blacklist': 'blacklist',
    'passlist': 'passlist',
}

def sanitize_mirror_url(url):
    url = re.sub(r'^(https?://)', '', url)
    url = re.sub(r'/$', '', url)
    return url + '/gh'

def is_valid_ip(ip):
    try:
        socket.inet_pton(socket.AF_INET, ip)
    except socket.error:
        try:
            socket.inet_pton(socket.AF_INET6, ip)
        except socket.error:
            return False
    return True

# 添加对 ENV_DEBUG_MODE 环境变量的支持
ENV_DEBUG_MODE = int(os.getenv('DEBUG_MODE', 0))
ENV_JSDELIVR = int(os.getenv('ENABLE_JSDELIVR', 0))
ENV_JSDELIVR_MIRROR = sanitize_mirror_url(os.getenv('SDELIVR_MIRROR', 'cdn.jsdelivr.net'))
ENV_SIZE_LIMIT = int(os.getenv('SIZE_LIMIT', 1024 * 1024 * 1024 * 999))
HOST = os.getenv('HOST', '127.0.0.1')
PORT = int(os.getenv('PORT', 80))
ASSET_URL = os.getenv('ASSET_URL', 'https://benzbrake.github.io/gh-proxy')

def env_int(name, default, minimum=None):
    value = os.getenv(name)
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    return parsed

def env_float(name, default, minimum=None):
    value = os.getenv(name)
    try:
        parsed = float(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    return parsed

ENV_API_PROXY = os.getenv('API_PROXY', '').strip()
ENV_API_PROXY_SECONDARY = os.getenv('API_PROXY_SECONDARY', '').strip()
ENV_API_PROXY_RETRIES = env_int('API_PROXY_RETRIES', 3, minimum=1)
ENV_API_PROXY_TIMEOUT = env_float('API_PROXY_TIMEOUT', 15, minimum=1)

# 根据 ENV_DEBUG_MODE 配置日志级别
if ENV_DEBUG_MODE:
    logging.basicConfig(format='%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s',
                        level=logging.DEBUG)
else:
    logging.basicConfig(format='%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s',
                        level=logging.INFO)

if not is_valid_ip(HOST):
    raise ValueError(f'Invalid IP address: {HOST}')

def download_rules_list(env_var_name, rule_type, url=None):
    """
    Load rules from URL or local file with backward compatibility support.

    Args:
        env_var_name: Environment variable name for custom URL
        rule_type: Rule type ('whitelist', 'blacklist', or 'passlist')
        url: Default URL to download rules from (optional)

    Returns:
        List of rule tuples
    """
    # Check for custom URL from environment variable
    custom_url = os.getenv(env_var_name)
    if custom_url:
        url = custom_url

    # Try downloading from URL if file doesn't exist
    if url and not os.path.exists(DEFAULT_RULES[rule_type]):
        try:
            response = requests.get(url)
            response.raise_for_status()
            rules = [tuple([x.replace(' ', '') for x in line.strip().split('/')]) for line in response.text.split('\n') if line.strip() and not line.strip().startswith('#')]
            with open(DEFAULT_RULES[rule_type], 'w') as file:
                file.write('\n'.join('/'.join(rule) for rule in rules))
            return rules
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch rules list from {url}: {e}. Using an empty list.")
            return []

    # Load from resources directory with fallback to root directory (backward compatibility)
    rule_file = DEFAULT_RULES[rule_type]
    if not os.path.exists(rule_file):
        rule_file = LEGACY_RULES[rule_type]

    if os.path.exists(rule_file):
        with open(rule_file, 'r') as file:
            return [tuple([x.replace(' ', '') for x in line.strip().split('/')]) for line in file.readlines() if line.strip() and not line.strip().startswith('#')]

    print(f"Local file {rule_file} not found. Using an empty list.")
    return []


whitelist_rules = download_rules_list('WHITELIST_RULES_URL', 'whitelist')
blacklist_rules = download_rules_list('BLACKLIST_RULES_URL', 'blacklist', 'https://github.com/benzBrake/gh-proxy/raw/master/resources/blacklist_rules')
passlist_rules = download_rules_list('PASSLIST_RULES_URL', 'passlist')

app = Flask(__name__)
CHUNK_SIZE = 1024 * 10
HOP_BY_HOP_HEADERS = {
    'connection',
    'keep-alive',
    'proxy-authenticate',
    'proxy-authorization',
    'proxy-connection',
    'te',
    'trailer',
    'transfer-encoding',
    'upgrade',
}

# 缓存静态资源，提供默认值防止启动失败
try:
    index_html = requests.get(ASSET_URL, timeout=10).text
    icon_r = requests.get(ASSET_URL + '/favicon.ico', timeout=10).content
    forbidden_html = requests.get(ASSET_URL + '/forbidden.html', timeout=10).text
    logging.info(f'Static resources cached from {ASSET_URL}')
except requests.RequestException as e:
    logging.warning(f'Failed to fetch static resources from {ASSET_URL}: {e}')
    index_html = '<h1>gh-proxy Service</h1><p>Failed to load index page</p>'
    icon_r = b''
    forbidden_html = '<h1>Forbidden</h1><p>Your access has been denied.</p>'
exp1 = re.compile(r'^(?:https?://)?github\.com/(?P<author>.+?)/(?P<repo>.+?)/(?:releases|archive)/.*$')
exp2 = re.compile(r'^(?:https?://)?github\.com/(?P<author>.+?)/(?P<repo>.+?)/(?:blob|raw)/.*$')
exp3 = re.compile(r'^(?:https?://)?github\.com/(?P<author>.+?)/(?P<repo>.+?)/(?:info|git-).*$')
exp4 = re.compile(r'^(?:https?://)?raw\.(?:githubusercontent|github)\.com/(?P<author>.+?)/(?P<repo>.+?)/.+?/.+$')
exp5 = re.compile(r'^(?:https?://)?gist\.(?:githubusercontent|github)\.com/(?P<author>.+?)/.+?/.+$')
exp6 = re.compile(r'^(?:https?://)?api\.github\.com/repos/(?P<author>.+?)/(?P<repo>.+?)/.*$')
exp7 = re.compile(r'^(?:https?://)?api\.github\.com/users/(?P<author>[^/]+)(/.*?)?$')

requests.sessions.default_headers = lambda: CaseInsensitiveDict()

logging.basicConfig(format='%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s',
                    level=logging.DEBUG)

@app.route('/')
def index():
    if 'q' in request.args:
        return redirect('/' + request.args.get('q'))
    return index_html

@app.route('/favicon.ico')
def icon():
    return Response(icon_r, content_type='image/vnd.microsoft.icon')

def iter_content(self, chunk_size=1, decode_unicode=False):
    def generate():
        if hasattr(self.raw, 'stream'):
            try:
                for chunk in self.raw.stream(chunk_size, decode_content=False):
                    yield chunk
            except ProtocolError as e:
                raise ChunkedEncodingError(e)
            except DecodeError as e:
                raise ContentDecodingError(e)
            except ReadTimeoutError as e:
                raise ConnectionError(e)
        else:
            while True:
                chunk = self.raw.read(chunk_size)
                if not chunk:
                    break
                yield chunk

        self._content_consumed = True

    if self._content_consumed and isinstance(self._content, bool):
        raise StreamConsumedError()
    elif chunk_size is not None and not isinstance(chunk_size, int):
        raise TypeError("chunk_size must be an int, it is instead a %s." % type(chunk_size))

    reused_chunks = iter_slices(self._content, chunk_size)
    stream_chunks = generate()
    chunks = reused_chunks if self._content_consumed else stream_chunks

    if decode_unicode:
        chunks = stream_decode_response_unicode(chunks, self)

    return chunks

def check_url(u):
    for exp in (exp1, exp2, exp3, exp4, exp5, exp6, exp7):
        m = exp.match(u)
        if m:
            return m
    return False

def sanitize_response_headers(headers):
    sanitized = {}
    for key, value in headers.items():
        if key.lower() in HOP_BY_HOP_HEADERS:
            continue
        sanitized[key] = value
    return sanitized

def build_requests_proxy(proxy_url):
    if not proxy_url:
        return None
    return {
        'http': proxy_url,
        'https': proxy_url,
    }

def is_github_api_url(url):
    return urlparse(url).netloc.lower() == 'api.github.com'

def is_retryable_method(method):
    return method.upper() in {'GET', 'HEAD', 'OPTIONS'}

def should_retry_github_api_response(response, method):
    if not is_retryable_method(method):
        return False
    if response.status_code in {429, 500, 502, 503, 504}:
        return True
    if response.status_code != 403:
        return False
    if response.headers.get('Retry-After'):
        return True
    if response.headers.get('X-RateLimit-Remaining') == '0':
        return True
    return bool(response.headers.get('X-RateLimit-Reset'))

def github_api_request(method, url, headers, data, allow_redirects):
    strategies = []
    primary_proxy = build_requests_proxy(ENV_API_PROXY)
    secondary_proxy = build_requests_proxy(ENV_API_PROXY_SECONDARY)

    if primary_proxy:
        strategies.append(('primary-proxy', primary_proxy, ENV_API_PROXY_RETRIES))
    if secondary_proxy and secondary_proxy != primary_proxy:
        strategies.append(('secondary-proxy', secondary_proxy, ENV_API_PROXY_RETRIES))
    strategies.append(('direct', None, 1))

    for strategy_index, (strategy_name, proxies, max_attempts) in enumerate(strategies):
        for attempt in range(1, max_attempts + 1):
            try:
                logging.info(
                    'github api request strategy=%s attempt=%s/%s url=%s',
                    strategy_name, attempt, max_attempts, url)
                response = requests.request(
                    method=method,
                    url=url,
                    data=data,
                    headers=headers,
                    stream=True,
                    allow_redirects=allow_redirects,
                    proxies=proxies,
                    timeout=ENV_API_PROXY_TIMEOUT)
                is_last_attempt = strategy_index == len(strategies) - 1 and attempt == max_attempts
                if should_retry_github_api_response(response, method) and not is_last_attempt:
                    logging.warning(
                        'github api retryable response strategy=%s attempt=%s/%s status=%s url=%s',
                        strategy_name, attempt, max_attempts, response.status_code, url)
                    response.close()
                    continue
                return response
            except requests.exceptions.RequestException as exc:
                logging.warning(
                    'github api request failed strategy=%s attempt=%s/%s url=%s error=%s',
                    strategy_name, attempt, max_attempts, url, exc)
                if strategy_index == len(strategies) - 1 and attempt == max_attempts:
                    raise

    raise RuntimeError('unreachable github api request state')

@app.route('/<path:u>', methods=['GET', 'POST'])
def handler(u):
    u = u if u.startswith('http') else 'https://' + u
    if u.rfind('://', 3, 9) == -1:
        u = u.replace('s:/', 's://', 1)

    pass_by = False
    m = check_url(u)

    if m:
        m = tuple(m.groups())
        if whitelist_rules:
            for i in whitelist_rules:
                if m[:len(i)] == i or i[0] == '*' and len(m) == 2 and m[1] == i[1]:
                    break
            else:
                return Response(forbidden_html, status=403, content_type='text/html; charset=UTF-8')

        for i in blacklist_rules:
            if m[:len(i)] == i or i[0] == '*' and len(m) == 2 and m[1] == i[1]:
                return Response(forbidden_html, status=403, content_type='text/html; charset=UTF-8')

        for i in passlist_rules:
            if m[:len(i)] == i or i[0] == '*' and len(m) == 2 and m[1] == i[1]:
                pass_by = True
                break
    else:
        return Response('Invalid input.', status=403)

    if (ENV_JSDELIVR or pass_by) and exp2.match(u):
        u = u.replace('/blob/', '@', 1).replace('github.com', ENV_JSDELIVR_MIRROR, 1)
        return redirect(u)
    elif (ENV_JSDELIVR or pass_by) and exp4.match(u):
        u = re.sub(r'(\.com/.*?/.+?)/(.+?/)', r'\1@\2', u, 1)
        _u = u.replace('raw.githubusercontent.com', ENV_JSDELIVR_MIRROR, 1)
        u = u.replace('raw.github.com', ENV_JSDELIVR_MIRROR, 1) if _u == u else _u
        return redirect(u)
    else:
        if exp2.match(u):
            u = u.replace('/blob/', '/raw/', 1)
        if pass_by:
            url = u + request.url.replace(request.base_url, '', 1)
            if url.startswith('https:/') and not url.startswith('https://'):
                url = 'https://' + url[7:]
            return redirect(url)
        u = quote(u, safe='/:')
        return proxy(u)

def proxy(u, allow_redirects=False):
    headers = {}
    r_headers = dict(request.headers)
    if 'Host' in r_headers:
        r_headers.pop('Host')
    try:
        url = u + request.url.replace(request.base_url, '', 1)
        if url.startswith('https:/') and not url.startswith('https://'):
            url = 'https://' + url[7:]

        logging.info('proxy: %s' % url)
        if is_github_api_url(url):
            r = github_api_request(
                method=request.method,
                url=url,
                headers=r_headers,
                data=request.data,
                allow_redirects=allow_redirects)
        else:
            r = requests.request(
                method=request.method,
                url=url,
                data=request.data,
                headers=r_headers,
                stream=True,
                allow_redirects=allow_redirects)
        headers = sanitize_response_headers(r.headers)

        if 'Content-length' in r.headers and int(r.headers['Content-length']) > ENV_SIZE_LIMIT:
            return redirect(u + request.url.replace(request.base_url, '', 1))

        def generate():
            try:
                for chunk in iter_content(r, chunk_size=CHUNK_SIZE):
                    yield chunk
            finally:
                r.close()

        if 'Location' in r.headers:
            _location = r.headers.get('Location')
            if check_url(_location):
                headers['Location'] = '/' + _location
            else:
                return proxy(_location, True)

        return Response(generate(), headers=headers, status=r.status_code)
    except Exception as e:
        headers['content-type'] = 'text/html; charset=UTF-8'
        return Response('server error ' + str(e), status=500, headers=headers)

app.debug = ENV_DEBUG_MODE == 1
if __name__ == '__main__':
    app.run(host=HOST, port=PORT)
