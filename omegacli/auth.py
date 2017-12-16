# source https://djangosnippets.org/snippets/2727/
from requests.auth import AuthBase


class TastypieApiKeyAuth(AuthBase):

    """
    Sets the appropriate authentication headers
    for the Tastypie API key authentication.

    Usage:
        auth = TastypieApiKeyAuth('jezdez', 
                                  '25fdd0d9d210acb78b5b845fe8284a3c93630252')
        response = requests.get('http://api.foo.bar/v1/spam/', auth=auth)
    """
    def __init__(self, username, api_key):
        self.username = username
        self.api_key = api_key

    def __call__(self, r):
        r.headers['Authorization'] = 'ApiKey %s:%s' % (
            self.username, self.api_key)
        return r
