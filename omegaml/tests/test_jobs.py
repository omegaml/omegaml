from __future__ import absolute_import

import os
import tempfile
from unittest import TestCase

import gridfs
from nbformat import write, v4

from omegaml import Omega
from omegaml.documents import Metadata
from omegaml.util import settings as omegaml_settings


class JobTests(TestCase):

    def setup(self):
        TestCase.setUp(self)

    def tearDown(self):
        TestCase.tearDown(self)
        for fn in self.om.jobs.list():
            self.om.jobs.drop(fn)

    @property
    def om(self):
        om = Omega()
        return om

    @property
    def fs(self):
        om = self.om
        defaults = omegaml_settings()
        fs = om.jobs.get_fs(defaults.OMEGA_NOTEBOOK_COLLECTION)
        return fs

    def test_job_put_get(self):
        """
        test job put and get
        """
        om = self.om
        # create a notebook
        cells = []
        code = "print 'hello'"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put the notebook
        meta = om.jobs.put(notebook, 'testjob')
        self.assertEqual(meta.name, 'testjob.ipynb')
        # read it back and see what's in it
        notebook2 = om.jobs.get('testjob')
        self.assertDictEqual(notebook2, notebook)

    def test_job_list(self):
        """
        test job listing
        """
        fs = self.fs
        om = self.om
        # create a notebook
        cells = []
        code = "print 'hello'"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put the notebook
        meta = om.jobs.put(notebook, 'testjob')
        self.assertEqual(meta.name, 'testjob.ipynb')
        nb = v4.new_notebook(cells=cells)
        job_list = self.om.jobs.list()
        expected = 'testjob.ipynb'
        self.assertIn(expected, job_list)

    def test_run_job_valid(self):
        """
        test running a valid job 
        """
        om = self.om
        # create a notebook
        cells = []
        code = "print('hello')"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put the notebook
        meta = om.jobs.put(notebook, 'testjob')
        self.assertEqual(meta.name, 'testjob.ipynb')
        meta_job = om.jobs.run('testjob')
        self.assertIn('job_results', meta_job.attributes)
        self.assertIn('job_runs', meta_job.attributes)
        runs = meta_job.attributes['job_runs']
        results = meta_job.attributes['job_results']
        self.assertEqual(len(runs), 1)
        self.assertEqual(len(results), 1)
        resultnb = results[0]
        self.assertTrue(om.jobs.exists(resultnb))
        self.assertEqual(runs[0]['results'], resultnb)

    def test_run_job_invalid(self):
        """
        test running an invalid job
        """
        fs = self.fs
        om = self.om
        # create a notebook
        cells = []
        code = "INVALID PYTHON CODE"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put the notebook
        meta = om.jobs.put(notebook, 'testjob')
        self.assertEqual(meta.name, 'testjob.ipynb')
        nb = v4.new_notebook(cells=cells)
        meta_job = om.jobs.run('testjob')
        runs = meta_job.attributes['job_runs']
        self.assertEqual(len(runs), 1)
        self.assertEqual('ERROR', runs[0]['status'])

    def test_run_nonexistent_job(self):
        om = self.om
        self.assertRaises(
            gridfs.errors.NoFile, om.jobs.run_notebook, 'dummys.ipynb')

    def test_scheduled_job(self):
        om = self.om
        fs = om.jobs.get_fs()
        dummy_nb_file = tempfile.NamedTemporaryFile().name
        cells = []
        conf = """
        # omega-ml:
        #   run-at: "*/5 * * * *"
        """.strip()
        cmd = "print('hello')"
        cells.append(v4.new_code_cell(source=conf))
        cells.append(v4.new_code_cell(source=cmd))
        notebook = v4.new_notebook(cells=cells)
        # check we have a valid configuration object
        meta = om.jobs.put(notebook, 'testjob')
        config = om.jobs.get_notebook_config('testjob')
        self.assertIn('run-at', config)
        self.assertIn('config', meta.attributes)
        self.assertIn('run-at', meta.attributes['config'])
        # check the job was scheduled
        self.assertIn('triggers', meta.attributes)
        trigger = meta.attributes['triggers'][-1]
        self.assertEqual(trigger['status'], 'PENDING')

        # run it as scheduled, check it is ok
        def get_trigger(event=None):
            # get last trigger or specified by event
            meta = om.jobs.metadata('testjob')
            triggers = meta.attributes['triggers']
            if not event:
                trigger = triggers[-1]
            else:
                trigger = [t for t in triggers if t['event'] == event][0]
            return trigger

        def assert_pending(event=None):
            trigger = get_trigger(event)
            self.assertEqual(trigger['status'], 'PENDING')

        def assert_ok(event=None):
            trigger = get_trigger(event)
            self.assertEqual(trigger['status'], 'OK')

        assert_pending()
        # -- run by the periodic task. note we pass now= as to simulate a time
        om.runtime.task('omegaml.notebook.tasks.execute_scripts').run(now=trigger['run-at'])
        assert_ok(event=trigger['event'])
        # -- it should be pending again
        assert_pending()
        # execute the scheduled job by event name
        trigger = get_trigger()
        om.runtime.job('testjob').run(event=trigger['event'])
        # the last run should be ok, and there should not be a new pending event
        # since we did not reschedule
        assert_ok()
        with self.assertRaises(AssertionError):
            assert_pending()
        # reschedule explicit and check we have a pending event
        om.runtime.job('testjob').schedule().get()
        assert_pending()
