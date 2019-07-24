istrue = lambda v: (
    (v.lower() in ('yes', '1', 'y', 'true', 't'))
    if isinstance(v, str) else bool(v)
)
isfalse = lambda v: not istrue(v)

def uri(browser, uri):
    """ given a browser, replace the path with uri """
    from six.moves.urllib.parse import urlparse, urlunparse
    url = browser.url
    parsed = list(urlparse(url))
    parsed[2] = uri
    return urlunparse(parsed)


