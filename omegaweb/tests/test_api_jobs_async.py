from django.contrib.auth.models import User
from django.test import TestCase
from nbformat import v4
from tastypie.test import ResourceTestCaseMixin

from omegaml import Omega
from omegaops import get_client_config
from omegaweb.tests.util import OmegaResourceTestMixin


class JobResourceTestsAsync(OmegaResourceTestMixin, ResourceTestCaseMixin, TestCase):
    fixtures = ['landingpage']

    def setUp(self):
        super(JobResourceTestsAsync, self).setUp()
        # self.api_client = ClientRequestTracer(self.api_client, response=False)
        # setup django user
        self.username = username = 'test'
        self.email = email = 'test@omegaml.io'
        self.password = password = 'password'
        self.user = User.objects.create_user(username, email, password)
        self.apikey = self.user.api_key.key
        # setup omega credentials
        self.setup_initconfig()
        # setup test data
        config = get_client_config(self.user)
        om = self.om = Omega(mongo_url=config.get('OMEGA_MONGO_URL'))
        for ds in om.datasets.list():
            om.datasets.drop(ds)
        for ds in om.jobs.list():
            om.jobs.drop(ds)

    def tearDown(self):
        pass

    def url(self, pk=None, action=None, query=None):
        url = '/api/v1/job/'
        if pk is not None:
            url += '{pk}/'.format(**locals())
        if action is not None:
            url += '{action}/'.format(**locals())
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

    def get_credentials(self):
        return self.create_apikey(self.username, self.apikey)

    def test_job_run(self):
        om = self.om
        # create a notebook
        cells = []
        code = "print('hello')"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put notebook
        meta = om.jobs.put(notebook, 'testjob')
        # run the job on the cluster
        resp = self.api_client.post(self.url('testjob', action='run'),
                                    authentication=self.get_credentials(),
                                    **self._async_headers)

        resp = self._check_async(resp)
        self.assertHttpOK(resp)
        data = self.deserialize(resp)['response']
        self.assertIn('created', data)
        self.assertEqual(len(data['job_results']), 1)
        self.assertEqual(len(data['job_runs']), 1)
        # get job info for results
        resultsjob = data['job_results'][0]
        resp = self.api_client.get(self.url(resultsjob),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('source_job', data)
