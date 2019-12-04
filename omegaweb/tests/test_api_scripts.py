import os

import sys
from unittest import skip

from django.contrib.auth.models import User
from landingpage.models import ServicePlan
from omegaml import Omega
from omegaops import add_user, add_service_deployment, get_client_config
from tastypie.test import ResourceTestCase
from tastypiex.requesttrace import ClientRequestTracer


class ScriptResourceTests(ResourceTestCase):
    def setUp(self):
        super(ScriptResourceTests, self).setUp()
        # self.api_client = ClientRequestTracer(self.api_client, response=False)
        # setup django user
        self.username = username = 'test'
        self.email = email = 'test@omegaml.io'
        self.password = password = 'password'
        self.user = User.objects.create_user(username, email, password)
        self.apikey = self.user.api_key.key
        # setup omega credentials
        # FIXME refactor to remove dependency to landingpage (omegaweb should
        # have an injectable config module of sorts)
        ServicePlan.objects.create(name='omegaml')
        init_config = {
            'dbname': 'testdb',
            'username': self.user.username,
            'password': 'foobar',
        }
        self.config = add_user(init_config['username'],
                               init_config['password'], dbname=init_config['dbname'])
        add_service_deployment(self.user, self.config)
        # setup test data
        config = get_client_config(self.user)
        om = self.om = Omega(mongo_url=config.get('OMEGA_MONGO_URL'))
        for ds in om.scripts.list():
            om.scripts.drop(ds)
        self.api_client = ClientRequestTracer(self.api_client, response=False)

    def tearDown(self):
        pass

    def url(self, pk=None, action=None, query=None):
        url = '/api/v1/script/'
        if pk is not None:
            url += '{pk}/'.format(**locals())
        if action is not None:
            url += '{action}/'.format(**locals())
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

    def get_credentials(self):
        return self.create_apikey(self.username, self.apikey)

    def test_script_run(self):
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'helloworld'))
        om = self.om
        pkg = 'pkg://{}'.format(pkgpath)
        # put script
        meta = om.scripts.put(pkg, 'helloworld')
        # run the script on the cluster
        resp = self.api_client.post(self.url('helloworld', action='run', query='text=foo'),
                                    authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('runtimes', data)
        self.assertIn('result', data)
        expected = list(['hello from helloworld', {'text': 'foo', 'pure_python': False}])
        self.assertEqual(data['result'], expected)
