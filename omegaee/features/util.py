import os

import yaml


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


def get_admin_secrets(url=None):
    secrets = os.path.join(os.path.expanduser('~/.omegaml/behave.yml'))
    with open(secrets) as fin:
        secrets = yaml.safe_load(fin)
        secrets = secrets.get(url) or secrets
    return secrets['admin_user'], secrets['admin_password']
