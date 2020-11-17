from time import sleep
from unittest import TestCase

import os

import nbformat

from omegaml import Omega
from omegaml.tests.cli.scenarios import CliTestScenarios
from omegaml.tests.util import OmegaTestMixin
from omegaml.util import temp_filename


class CliJobsTest(CliTestScenarios, OmegaTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.om = Omega()
        self.clean()

    def test_cli_jobs_list(self):
        self.cli('jobs list')
        self.assertLogContains('info', '[]')
        self.create_job('test')
        self.cli('jobs list')
        self.assertLogContains('info', 'test.ipynb')

    def test_cli_jobs_get(self):
        self.create_job('test')
        fn = temp_filename(ext='ipynb')
        self.cli(f'jobs get test {fn}')
        self.assertTrue(os.path.exists(fn))
        with open(fn, 'r') as fin:
            nb = nbformat.read(fin, as_version=4)
        self.assertIn('cells', nb)
        self.assertIn('hello', nb['cells'][0]['source'])

    def test_cli_jobs_put(self):
        self.assertNotIn('test', self.om.jobs.list())
        cells = []
        code = "print 'hello'"
        cells.append(nbformat.v4.new_code_cell(source=code))
        notebook = nbformat.v4.new_notebook(cells=cells)
        fn = temp_filename(ext='ipynb')
        with open(fn, 'w') as fout:
            nbformat.write(notebook, fout, version=4)
        self.cli(f'jobs put {fn} test')
        self.assertLogContains('info', 'Metadata')
        self.assertLogContains('info', 'name=test')
        self.assertIn('test.ipynb', self.om.jobs.list())

    def test_cli_jobs_drop(self):
        cells = []
        code = "print 'hello'"
        cells.append(nbformat.v4.new_code_cell(source=code))
        notebook = nbformat.v4.new_notebook(cells=cells)
        self.om.jobs.put(notebook, 'testnb')
        self.cli(f'jobs drop testnb')
        expected = self.pretend_log('True')
        self.assertLogContains('info', expected)
        self.assertNotIn('testnb', self.om.jobs.list())

    def test_cli_jobs_metadata(self):
        self.create_job('test')
        self.cli('jobs metadata test')
        expected = self.pretend_log('"kind": "script.ipynb"')
        self.assertLogContains('info', expected)
        expected = self.pretend_log('"name": "test.ipynb"')
        self.assertLogContains('info', expected)

    def test_cli_jobs_schedule(self):
        self.create_job('test')
        # test there is an input prompt
        self.cli('jobs schedule test now', askfn=lambda *a, **kw: 'y')
        self.assertLogContains('info', 'test will be scheduled to run Every minute')
        # test there is no input prompt
        self.cli('jobs schedule test now -q', new_start=True)
        self.assertLogContains('info', 'Currently test is scheduled at Every minute')
        self.assertLogContains('info', 'test is scheduled to run next at')
        # test scheduled can be shown
        self.cli('jobs schedule test show', new_start=True)
        self.assertLogContains('info', 'test is scheduled to run next at')
        # test we can delete the job schedule
        # test there is an input prompt
        self.cli('jobs schedule test delete', askfn=lambda *a, **kw: 'y', new_start=True)
        self.cli('jobs schedule test show', new_start=True)
        self.assertLogContains('info', 'Currently test is not scheduled')
        # test we can see executed jobs
        self.cli('jobs schedule test now', askfn=lambda *a, **kw: 'y')
        meta = self.om.jobs.metadata('test')
        triggers = meta.attributes['triggers']
        trigger = triggers[-1]
        kwargs = dict(now=trigger['run-at'])
        self.om.runtime.task('omegaml.notebook.tasks.execute_scripts').apply_async(kwargs=kwargs).get()
        self.cli('jobs status test', new_start=True)
        entries =  self.get_log('info')
        # entries example - a list of args tuples passed to logger.info(*args)
        #   [('Runs:',), ('  2019-11-15 18:32:28.625000 OK ',),
        #   ('Next scheduled runs:',), ('   PENDING scheduled 2019-11-15T18:34:00',)]
        self.assertIn('Runs:', entries[0][0])
        self.assertIn('OK', entries[1][0])
        self.assertIn('Next scheduled runs:', entries[2][0])
        self.assertIn('PENDING', entries[3][0])
