from unittest import TestCase

from omegaml.client.auth import OmegaRestApiAuth


class OmegaRestApiAuthTests(TestCase):
    def test_omegaauth(self):
        """ test OmegaRestApiAuth works ok
        """
        auth = OmegaRestApiAuth("foo", "bar")
        self.assertEqual(auth.username, 'foo')
        self.assertEqual(auth.apikey, 'bar')
        self.assertEqual(repr(auth), 'OmegaRestApiAuth(username=foo, apikey="*****",qualifier=default)')

    def test_omegaauth_qualifier(self):
        auth = OmegaRestApiAuth("foo", "bar", qualifier='xyz')
        self.assertEqual(auth.username, 'foo')
        self.assertEqual(auth.apikey, 'bar')
        self.assertEqual(repr(auth), 'OmegaRestApiAuth(username=foo, apikey="*****",qualifier=xyz)')

    def test_omegaauth_headers(self):
        class Request:
            headers = {}

        auth = OmegaRestApiAuth("foo", "bar", qualifier='xyz')
        self.assertEqual(auth.get_credentials(), 'ApiKey foo:bar')
        r = Request()
        auth(r)
        self.assertEqual(r.headers['Authorization'], 'ApiKey foo:bar')
        self.assertEqual(r.headers['Qualifier'], 'xyz')

