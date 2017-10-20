from tastypie.test import ResourceTestCase


class ClientConfigResourceTests(ResourceTestCase):

    def setUp(self):
        ResourceTestCase.setUp(self)

    def tearDown(self):
        ResourceTestCase.tearDown(self)

    def url(self, pk=None, query=None):
        url = '/api/v1/config/'
        if pk is not None:
            url += pk + '/'
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

    def test_get_config(self):
        resp = self.api_client.get(self.url('sample'))
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('data', data)