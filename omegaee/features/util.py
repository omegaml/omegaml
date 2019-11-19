import os

import yaml

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


def find_user_apikey(br):
    for el in br.find_by_css('p'):
        if 'userid' in el.text:
            userid, apikey = el.text.split('\n')
            userid = userid.split(' ')[1]
            apikey = apikey.split(' ')[1]
    return userid, apikey


def get_admin_secrets(url=None):
    try:
        secrets = os.path.join(os.path.expanduser('~/.omegaml/behave.yml'))
        with open(secrets) as fin:
            secrets = yaml.safe_load(fin)
            secrets = secrets.get(url) or secrets
    except:
        secrets = {
            'admin_user': 'admin',
            'admin_password': 'test',
        }
    return secrets['admin_user'], secrets['admin_password']

def handle_alert(br):
    try:
        alert = br.get_alert()
        if alert:
            alert.accept()
    except:
        pass

def clear_om(om):
    for omstore in (om.datasets, om.jobs, om.models):
        [omstore.drop(name) for name in omstore.list()]