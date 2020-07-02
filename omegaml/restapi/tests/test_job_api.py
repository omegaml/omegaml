from unittest import TestCase
from urllib.parse import quote

from nbformat import v4

from omegaml import Omega
from omegaml.client.auth import OmegaRestApiAuth
from omegaml.restapi.app import app
from omegaml.restapi.tests.util import RequestsLikeTestClient
from omegaml.tests.util import OmegaTestMixin


class JobResourceTests(OmegaTestMixin, TestCase):
    def setUp(self):
        self.client = RequestsLikeTestClient(app)
        self.om = Omega()
        self.auth = OmegaRestApiAuth('user', 'pass')
        self.clean()

    def tearDown(self):
        pass

    def url(self, pk=None, action=None, query=None):
        url = '/api/v1/job/'
        if pk is not None:
            url += '{pk}/'.format(pk=quote(pk, safe='')) # encode / in name
        if action is not None:
            url += '{action}'.format(**locals())
        if query is not None:
            url += '?{query}'.format(**locals())
        return url

    def test_get_job_info(self):
        om = self.om
        # create a notebook
        cells = []
        code = "print('hello')"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put notebook
        meta = om.jobs.put(notebook, 'testjob')
        resp = self.client.get(self.url('testjob'))
        self.assertHttpOK(resp)
        # see if we get job data
        data = self.deserialize(resp)
        self.assertIn('created', data)
        self.assertIn('job_results', data)
        self.assertIn('job_runs', data)
        self.assertIn('job', data)
        self.assertEqual(data['job'], 'testjob.ipynb')
        # run the job locally and see if we get results ok
        om.jobs.run('testjob')
        resp = self.client.get(self.url('testjob'))
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('created', data)
        self.assertEqual(len(data['job_results']), 1)
        self.assertEqual(len(data['job_runs']), 1)
        # get job info for results
        resultsjob = data['job_results'][0]
        resp = self.client.get(self.url(resultsjob))
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('source_job', data)

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
        resp = self.client.post(self.url('testjob', action='run'))
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('created', data)
        self.assertEqual(len(data['job_results']), 1)
        self.assertEqual(len(data['job_runs']), 1)
        # get job info for results
        resultsjob = data['job_results'][0]
        resp = self.client.get(self.url(resultsjob))
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('source_job', data)

    def test_job_run_async(self):
        om = self.om
        # create a notebook
        cells = []
        code = "print('hello')"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put notebook
        meta = om.jobs.put(notebook, 'testjob')
        # run the job on the cluster
        resp = self.client.post(self.url('testjob', action='run'),
                                headers=self._async_headers)
        resp = self._check_async(resp)
        self.assertHttpOK(resp)
        data = self.deserialize(resp)['response']
        self.assertIn('created', data)
        self.assertEqual(len(data['job_results']), 1)
        self.assertEqual(len(data['job_runs']), 1)
        # get job info for results
        resultsjob = data['job_results'][0]
        resp = self.client.get(self.url(resultsjob))
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('source_job', data)


