from landingpage.models import ServicePlan

from django.contrib.auth.models import User
from nbformat import v4
from tastypie.test import ResourceTestCase

from omegaml import Omega
from omegaops import add_user, add_service_deployment, get_client_config
from tastypiex.requesttrace import ClientRequestTracer


class JobResourceTests(ResourceTestCase):
    def setUp(self):
        super(JobResourceTests, self).setUp()
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

    def test_get_job_info(self):
        om = self.om
        # create a notebook
        cells = []
        code = "print('hello')"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put notebook
        meta = om.jobs.put(notebook, 'testjob')
        resp = self.api_client.get(self.url('testjob'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        # see if we get job data
        data = self.deserialize(resp)
        self.assertIn('created', data)
        self.assertIn('job_results', data)
        self.assertIn('job_runs', data)
        self.assertIn('name', data)
        self.assertEqual(data['name'], 'testjob.ipynb')
        # run the job locally and see if we get results ok
        om.jobs.run('testjob')
        resp = self.api_client.get(self.url('testjob'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
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
                                    authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
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

    def test_job_list(self):
        om = self.om
        # create a notebook
        cells = []
        code = "print('hello')"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put notebook
        meta = om.jobs.put(notebook, 'testjob')
        # see what we get
        resp = self.api_client.get(self.url(),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('objects', data)
        self.assertEqual(len(data['objects']), 1)

    def test_job_create(self):
        om = self.om
        # create a notebook
        cells = []
        code = "print('hello')"
        data = {
            'code': code,
        }
        # see what we get
        resp = self.api_client.post(self.url('testjob'), data=data,
                                    authentication=self.get_credentials())
        self.assertHttpCreated(resp)
        data = self.deserialize(resp)
        self.assertIn('created', data)
        self.assertIn('job_results', data)
        self.assertIn('job_runs', data)
        self.assertIn('name', data)
        self.assertEqual(data['name'], 'testjob.ipynb')

    def test_job_report(self):
        om = self.om
        # create a notebook
        cells = []
        code = "print('hello')"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put notebook
        meta = om.jobs.put(notebook, 'testjob')
        # see what we get
        resp = self.api_client.get(self.url('testjob', action='report'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('content', data)
        self.assertIn('name', data)
        self.assertIn('<html>', data['content'])

    def test_job_report_slides(self):
        om = self.om
        # create a notebook
        cells = []
        code = "print('hello')"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put notebook
        meta = om.jobs.put(notebook, 'testjob')
        # see what we get
        resp = self.api_client.get(self.url('testjob', action='report'),
                                   data=dict(format='slides'),
                                   authentication=self.get_credentials())
        self.assertHttpOK(resp)
        data = self.deserialize(resp)
        self.assertIn('content', data)
        self.assertIn('name', data)
        self.assertIn('<html>', data['content'])
        self.assertIn('Reveal.initialize', data['content'])
