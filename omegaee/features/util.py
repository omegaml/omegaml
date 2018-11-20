def uri(browser, uri):
    """ given a browser, replace the path with uri """
    from six.moves.urllib.parse import urlparse, urlunparse
    url = browser.url
    parsed = list(urlparse(url))
    parsed[2] = uri
    return urlunparse(parsed)


def find_user_apikey(br):
    for el in br.find_by_css('p'):
        if 'userid' in el.text:
            userid, apikey = el.text.split('\n')
            userid = userid.split(' ')[1]
            apikey = apikey.split(' ')[1]
    return userid, apikey
