

from __future__ import absolute_import
from unittest import TestCase
from omegaml import Omega
from omegaml.documents import Metadata
import tempfile
import gridfs
from nbformat import write, v4
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
        om = self.om
        # create a notebook
        cells = []
        code = "print 'hello'"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put the notebook
        meta = om.jobs.put(notebook, 'testjob')
        self.assertEqual(meta.name, 'testjob')
        # read it back and see what's in it
        notebook2 = om.jobs.get('testjob')
        self.assertDictEqual(notebook2, notebook)

    def test_job_list(self):
        fs = self.fs
        om = self.om
        # create a notebook
        cells = []
        code = "print 'hello'"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put the notebook
        meta = om.jobs.put(notebook, 'testjob')
        self.assertEqual(meta.name, 'testjob')
        nb = v4.new_notebook(cells=cells)
        job_list = self.om.jobs.list()
        expected = 'testjob'
        self.assertIn(expected, job_list)

    def test_job_run_invalid(self):
        om = Omega()
        defaults = omegaml_settings()
        fs = om.jobs.get_fs(defaults.OMEGA_NOTEBOOK_COLLECTION)
        dummy_nb_file = tempfile.NamedTemporaryFile().name
        cells = []
        code = "print 'hello'"
        nb_file = 'job_dummy.ipynb'
        cells.append(v4.new_code_cell(source=code))
        nb = v4.new_notebook(cells=cells)
        with open(dummy_nb_file, 'w') as f:
            write(nb, f, version=4)
        # upload job notebook
        with open(dummy_nb_file, 'rb') as f:
            fs.put(f.read(), filename=nb_file)
        self.assertRaises(ValueError, om.jobs.run_notebook, nb_file)

    def test_job_run_valid(self):
        om = Omega()
        defaults = omegaml_settings()
        fs = om.jobs.get_fs(defaults.OMEGA_NOTEBOOK_COLLECTION)
        dummy_nb_file = tempfile.NamedTemporaryFile().name
        cells = []
        conf = """
        # omegaml.script:
        #   run-at: "*/5 * * * *"
        #   results-store: gridfs
        #   author: exsys@nixify.com
        #   name: Gaurav Ghimire
        """
        cmd = "print 'hello'"
        nb_file = 'job_dummy.ipynb'
        cells.append(v4.new_code_cell(source=conf))
        cells.append(v4.new_code_cell(source=cmd))
        nb = v4.new_notebook(cells=cells)
        with open(dummy_nb_file, 'w') as f:
            write(nb, f, version=4)
        # upload job notebook
        with open(dummy_nb_file, 'rb') as f:
            fs.put(f.read(), filename=nb_file)
        result = om.jobs.run_notebook(nb_file)
        self.assertIsInstance(result, Metadata)

    def test_run_nonexistent_job(self):
        om = Omega()
        self.assertRaises(
            gridfs.errors.NoFile, om.jobs.run_notebook, 'dummys.ipynb')

    def test_job_status(self):
        om = Omega()
        defaults = omegaml_settings()
        fs = om.jobs.get_fs(defaults.OMEGA_NOTEBOOK_COLLECTION)
        dummy_nb_file = tempfile.NamedTemporaryFile().name
        cells = []
        conf = """
        # omegaml.script:
        #   run-at: "*/5 * * * *"
        #   results-store: gridfs
        #   author: exsys@nixify.com
        #   name: Gaurav Ghimire
        """
        cmd = "print 'hello'"
        nb_file = 'job_dummy.ipynb'
        cells.append(v4.new_code_cell(source=conf))
        cells.append(v4.new_code_cell(source=cmd))
        nb = v4.new_notebook(cells=cells)
        with open(dummy_nb_file, 'w') as f:
            write(nb, f, version=4)
        # upload job notebook
        with open(dummy_nb_file, 'rb') as f:
            fs.put(f.read(), filename=nb_file)
        om.jobs.run_notebook('job_dummy.ipynb')
        expected = Metadata.objects.filter(
            name='job_dummy.ipynb', kind__in=Metadata.KINDS)
        result = om.jobs.get_status('job_dummy.ipynb')
        self.assertIsInstance(result[0], Metadata)
        self.assertIsInstance(expected[0], Metadata)
