'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const test = require('node:test')
const vm = require('node:vm')

const source = fs.readFileSync('index.js', 'utf8')
const context = {
    Headers,
    Request,
    Response,
    URL,
    addEventListener() {},
    console,
    fetch,
}
vm.createContext(context)
vm.runInContext(
    source + '\n;globalThis.testSanitizeRequestHeaders = sanitizeRequestHeaders; globalThis.testFetchHandler = fetchHandler; globalThis.testProxy = proxy',
    context,
)

test('worker strips credentials and preserves download headers', () => {
    const input = new Headers({
        authorization: 'Bearer secret',
        cookie: 'session=secret',
        'proxy-authorization': 'Basic secret',
        'x-forwarded-for': '127.0.0.1',
        range: 'bytes=100-200',
        'x-github-api-version': '2022-11-28',
    })
    const sanitized = context.testSanitizeRequestHeaders(input)

    assert.equal(sanitized.get('authorization'), null)
    assert.equal(sanitized.get('cookie'), null)
    assert.equal(sanitized.get('proxy-authorization'), null)
    assert.equal(sanitized.get('x-forwarded-for'), null)
    assert.equal(sanitized.get('range'), 'bytes=100-200')
    assert.equal(sanitized.get('x-github-api-version'), '2022-11-28')
})

test('worker serves the configured frontend assets', async () => {
    const fetchedUrls = []
    context.fetch = async url => {
        fetchedUrls.push(String(url))
        return new Response('frontend')
    }
    const response = await context.testFetchHandler({ request: new Request('https://proxy.example/sw.js') })
    assert.equal(response.status, 200)
    assert.equal(await response.text(), 'frontend')
    assert.deepEqual(fetchedUrls, ['https://benzbrake.github.io/gh-proxy/sw.js'])
})

test('worker preserves upstream browser security headers', async () => {
    context.fetch = async () => new Response('ok', { headers: {
        'content-security-policy': "default-src 'none'",
        'content-security-policy-report-only': "script-src 'none'",
        'clear-site-data': '"cache"',
    } })
    const response = await context.testProxy(new URL('https://github.com/a/b/archive/main.zip'), {
        method: 'GET', headers: new Headers(), redirect: 'manual',
    })
    assert.equal(response.headers.get('content-security-policy'), "default-src 'none'")
    assert.equal(response.headers.get('content-security-policy-report-only'), "script-src 'none'")
    assert.equal(response.headers.get('clear-site-data'), '"cache"')
})
