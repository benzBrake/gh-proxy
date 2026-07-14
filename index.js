'use strict'

const FORWARDED_REQUEST_HEADERS = new Set([
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
])

function isSecureGitHubApiUrl(targetUrl) {
    if (!targetUrl) return false

    try {
        const url = targetUrl instanceof URL ? targetUrl : new URL(targetUrl)
        return url.protocol.toLowerCase() === 'https:' &&
            url.hostname.toLowerCase() === 'api.github.com' &&
            (url.port === '' || url.port === '443')
    } catch (err) {
        return false
    }
}

function sanitizeRequestHeaders(headers, targetUrl) {
    const allowAuthorization = isSecureGitHubApiUrl(targetUrl)
    const sanitized = new Headers()
    for (const [name, value] of headers) {
        const normalizedName = name.toLowerCase()
        if (FORWARDED_REQUEST_HEADERS.has(normalizedName) ||
            (normalizedName === 'authorization' && allowAuthorization))
            sanitized.set(name, value)
    }
    return sanitized
}

/**
 * static files (404.html, sw.js, conf.js)
 */
const DEFAULTS = {
    assetUrl: 'https://benzbrake.github.io/gh-proxy',
    prefix: '/',
    jsdelivrEnabled: false,
    whiteList: [],
    whitelistRulesUrl: '',
    blacklistRulesUrl: 'https://raw.githubusercontent.com/benzBrake/gh-proxy/master/resources/blacklist_rules',
    rulesRefreshInterval: 300,
    jsdelivrBaseUrl: 'https://cdn.jsdelivr.net/gh',
}

function getBinding(name, fallback) {
    const value = globalThis[name]
    return value === undefined || value === '' ? fallback : value
}

function getOptionalBinding(name, fallback) {
    return globalThis[name] === undefined ? fallback : globalThis[name]
}

function parseBoolean(value) {
    return ['1', 'true', 'yes', 'on'].includes(String(value).toLowerCase())
}

function parseWhiteList(value) {
    if (Array.isArray(value)) return value

    try {
        const parsed = JSON.parse(value)
        return Array.isArray(parsed) && parsed.every(item => typeof item === 'string')
            ? parsed
            : DEFAULTS.whiteList
    } catch (err) {
        console.warn('WHITE_LIST must be a JSON array of strings')
        return DEFAULTS.whiteList
    }
}

const ASSET_URL_VALUE = String(getBinding('ASSET_URL', DEFAULTS.assetUrl)).replace(/\/+$/, '') + '/'
const PREFIX_VALUE = getBinding('PREFIX', DEFAULTS.prefix)
const JSDELIVR_BASE_URL_VALUE = getBinding('JSDELIVR_BASE_URL', DEFAULTS.jsdelivrBaseUrl)
const whiteList = parseWhiteList(getBinding('WHITE_LIST', DEFAULTS.whiteList))
const WHITELIST_RULES_URL_VALUE = getOptionalBinding('WHITELIST_RULES_URL', DEFAULTS.whitelistRulesUrl)
const BLACKLIST_RULES_URL_VALUE = getOptionalBinding('BLACKLIST_RULES_URL', DEFAULTS.blacklistRulesUrl)
const RULES_REFRESH_INTERVAL_VALUE = Math.max(60, Number(getBinding('RULES_REFRESH_INTERVAL', DEFAULTS.rulesRefreshInterval)) || DEFAULTS.rulesRefreshInterval) * 1000
const Config = {
    jsdelivr: parseBoolean(getBinding('JSDELIVR_ENABLED', DEFAULTS.jsdelivrEnabled)),
}

let rulesCache = { expiresAt: 0, whitelist: [], blacklist: [] }
let rulesRefreshPromise = null

function parseRules(text) {
    return text.split(/\r?\n/)
        .map(line => line.trim().replace(/\s/g, ''))
        .filter(line => line && !line.startsWith('#'))
        .map(line => line.split('/').filter(Boolean))
        .filter(rule => rule.length === 1 || rule.length === 2)
}

async function fetchRules(url, fallback) {
    if (!url) return fallback
    try {
        const response = await fetch(url, { cf: { cacheTtl: Math.ceil(RULES_REFRESH_INTERVAL_VALUE / 1000), cacheEverything: true } })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return parseRules(await response.text())
    } catch (err) {
        console.warn(`Failed to fetch rules from ${url}: ${err.message}`)
        return fallback
    }
}

async function refreshRules(force = false) {
    if (!force && Date.now() < rulesCache.expiresAt) return rulesCache
    if (rulesRefreshPromise) return rulesRefreshPromise

    rulesRefreshPromise = (async () => {
        const [whitelist, blacklist] = await Promise.all([
            fetchRules(WHITELIST_RULES_URL_VALUE, rulesCache.whitelist),
            fetchRules(BLACKLIST_RULES_URL_VALUE, rulesCache.blacklist),
        ])
        rulesCache = { whitelist, blacklist, expiresAt: Date.now() + RULES_REFRESH_INTERVAL_VALUE }
        return rulesCache
    })().finally(() => { rulesRefreshPromise = null })
    return rulesRefreshPromise
}

/** @type {ResponseInit} */
const PREFLIGHT_INIT = {
    status: 204,
    headers: new Headers({
        'access-control-allow-origin': '*',
        'access-control-allow-methods': 'GET,POST,PUT,PATCH,TRACE,DELETE,HEAD,OPTIONS',
        'access-control-max-age': '1728000',
    }),
}


const exp1 = /^(?:https?:\/\/)?github\.com\/.+?\/.+?\/(?:releases|archive)\/.*$/i
const exp2 = /^(?:https?:\/\/)?github\.com\/.+?\/.+?\/(?:blob|raw)\/.*$/i
const exp3 = /^(?:https?:\/\/)?github\.com\/.+?\/.+?\/(?:info|git-).*$/i
const exp4 = /^(?:https?:\/\/)?raw\.(?:githubusercontent|github)\.com\/.+?\/.+?\/.+?\/.+$/i
const exp5 = /^(?:https?:\/\/)?gist\.(?:githubusercontent|github)\.com\/.+?\/.+?\/.+$/i
const exp6 = /^(?:https?:\/\/)?github\.com\/.+?\/.+?\/tags.*$/i
const exp7 = /^(?:https?:\/\/)?api\.github\.com\/repos\/.+?\/.+?\/.*$/i
const exp8 = /^(?:https?:\/\/)?api\.github\.com\/users\/[^/]+(?:\/.*?)?$/i

/**
 * @param {any} body
 * @param {number} status
 * @param {Object<string, string>} headers
 */
function makeRes(body, status = 200, headers = {}) {
    headers['access-control-allow-origin'] = '*'
    return new Response(body, { status, headers })
}


/**
 * @param {string} urlStr
 */
function newUrl(urlStr) {
    try {
        return new URL(urlStr)
    } catch (err) {
        return null
    }
}


addEventListener('fetch', e => {
    const ret = fetchHandler(e)
        .catch(err => makeRes('cfworker error:\n' + err.stack, 502))
    e.respondWith(ret)
})

addEventListener('scheduled', e => {
    e.waitUntil(refreshRules(true))
})


function checkUrl(u) {
    for (let i of [exp1, exp2, exp3, exp4, exp5, exp6, exp7, exp8]) {
        if (u.search(i) === 0) {
            return true
        }
    }
    return false
}

/**
 * @param {FetchEvent} e
 */
async function fetchHandler(e) {
    const req = e.request
    const urlStr = req.url
    const urlObj = new URL(urlStr)
    let path = urlObj.searchParams.get('q')
    if (path) {
        return Response.redirect('https://' + urlObj.host + PREFIX_VALUE + path, 301)
    }
    // cfworker 会把路径中的 `//` 合并成 `/`
    path = urlObj.href.slice(urlObj.origin.length + PREFIX_VALUE.length).replace(/^https?:\/+/, 'https://')
    if (checkUrl(path)) {
        const rules = await refreshRules()
        if (!isAllowed(path, rules)) return makeRes('blocked', 403)
    }
    if (path.search(exp1) === 0 || path.search(exp5) === 0 || path.search(exp6) === 0 || path.search(exp3) === 0 || path.search(exp7) === 0 || path.search(exp8) === 0) {
        return httpHandler(req, path)
    } else if (path.search(exp2) === 0) {
        if (Config.jsdelivr) {
            const newUrl = path.replace('/blob/', '@').replace(/^(?:https?:\/\/)?github\.com/, JSDELIVR_BASE_URL_VALUE)
            return Response.redirect(newUrl, 302)
        } else {
            path = path.replace('/blob/', '/raw/')
            return httpHandler(req, path)
        }
    } else if (path.search(exp4) === 0) {
        if (Config.jsdelivr) {
            const newUrl = path.replace(/(?<=com\/.+?\/.+?)\/(.+?\/)/, '@$1').replace(/^(?:https?:\/\/)?raw\.(?:githubusercontent|github)\.com/, JSDELIVR_BASE_URL_VALUE)
            return Response.redirect(newUrl, 302)
        }
        else {
            return httpHandler(req, path)
        }
    } else {
        return fetch(ASSET_URL_VALUE + path)
    }
}

function getRepository(urlStr) {
    const patterns = [
        /^(?:https?:\/\/)?github\.com\/([^/]+)\/([^/]+)\//i,
        /^(?:https?:\/\/)?raw\.(?:githubusercontent|github)\.com\/([^/]+)\/([^/]+)\//i,
        /^(?:https?:\/\/)?gist\.(?:githubusercontent|github)\.com\/([^/]+)(?:\/|$)/i,
        /^(?:https?:\/\/)?api\.github\.com\/repos\/([^/]+)\/([^/]+)(?:\/|$)/i,
        /^(?:https?:\/\/)?(?:api\.)?github\.com\/users\/([^/]+)(?:\/|$)/i,
    ]
    for (const pattern of patterns) {
        const match = urlStr.match(pattern)
        if (match) return match.slice(1).map(value => decodeURIComponent(value))
    }
    return null
}

function matchesRule(repository, rule) {
    if (!repository || !rule.length) return false
    if (rule.length === 1) return repository[0] === rule[0]
    return (rule[0] === '*' || repository[0] === rule[0]) && repository[1] === rule[1]
}

function isAllowed(urlStr, rules) {
    const repository = getRepository(urlStr)
    const legacyAllowed = !whiteList.length || whiteList.some(item => urlStr.includes(item))
    if (!legacyAllowed) return false
    if (rules.whitelist.length && !rules.whitelist.some(rule => matchesRule(repository, rule))) return false
    return !rules.blacklist.some(rule => matchesRule(repository, rule))
}


/**
 * @param {Request} req
 * @param {string} pathname
 */
function httpHandler(req, pathname) {
    const reqHdrRaw = req.headers

    // preflight
    if (req.method === 'OPTIONS' &&
        reqHdrRaw.has('access-control-request-headers')
    ) {
        return new Response(null, PREFLIGHT_INIT)
    }

    let urlStr = pathname
    if (urlStr.search(/^https?:\/\//) !== 0) {
        urlStr = 'https://' + urlStr
    }
    const urlObj = newUrl(urlStr)
    const reqHdrNew = sanitizeRequestHeaders(reqHdrRaw, urlObj)

    /** @type {RequestInit} */
    const reqInit = {
        method: req.method,
        headers: reqHdrNew,
        redirect: 'manual',
        body: req.body
    }
    return proxy(urlObj, reqInit)
}


/**
 *
 * @param {URL} urlObj
 * @param {RequestInit} reqInit
 */
async function proxy(urlObj, reqInit) {
    // Reapply the allowlist at every redirect boundary.
    reqInit.headers = sanitizeRequestHeaders(reqInit.headers, urlObj)
    const res = await fetch(urlObj.href, reqInit)
    const resHdrOld = res.headers
    const resHdrNew = new Headers(resHdrOld)

    const status = res.status

    if (resHdrNew.has('location')) {
        let _location = resHdrNew.get('location')
        if (checkUrl(_location))
            resHdrNew.set('location', PREFIX_VALUE + _location)
        else {
            reqInit.redirect = 'follow'
            return proxy(newUrl(_location), reqInit)
        }
    }
    resHdrNew.set('access-control-expose-headers', '*')
    resHdrNew.set('access-control-allow-origin', '*')

    return new Response(res.body, {
        status,
        headers: resHdrNew,
    })
}

