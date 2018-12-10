

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
        self.assertIn(list(runs.keys())[0], resultnb)

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
        self.assertIn('An error occurred', list(runs.values())[0])

    def test_run_nonexistent_job(self):
        om = self.om
        self.assertRaises(
            gridfs.errors.NoFile, om.jobs.run_notebook, 'dummys.ipynb')
