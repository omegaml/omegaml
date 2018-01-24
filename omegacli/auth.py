# source https://djangosnippets.org/snippets/2727/
from requests.auth import AuthBase


class OmegaRestApiAuth(AuthBase):

    """
    Sets the appropriate authentication headers
    for the Omega REST API key authentication.

    Usage:
        auth = OmegaRestApiAuth('jezdez', 
                         '25fdd0d9d210acb78b5b845fe8284a3c93630252')
        response = requests.get('http://api.foo.bar/v1/spam/', auth=auth)
    """
    def __init__(self, username, apikey):
        self.username = username
        self.apikey = apikey

    def get_credentials(self):
        return 'ApiKey %s:%s' % (self.username, self.apikey)

    def __call__(self, r):
        r.headers['Authorization'] = self.get_credentials()
        return r
