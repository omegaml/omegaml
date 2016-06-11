

from unittest import TestCase
import omegaml
from omegaml import Omega
from omegaml.documents import Metadata
import tempfile
import gridfs
from nbformat import write, v4
from omegaml.util import override_settings
override_settings(
    OMEGA_MONGO_URL='mongodb://localhost:27017/omegatest',
    OMEGA_NOTEBOOK_COLLECTION='ipynbtest'
)


class JobTests(TestCase):

    def setup(self):
        TestCase.setUp(self)

    def tearDown(self):
        TestCase.tearDown(self)

    def test_job_list(self):
        om = Omega()
        defaults = omegaml.settings()
        fs = om.jobs.get_fs(defaults.OMEGA_NOTEBOOK_COLLECTION)
        dummy_nb_file = tempfile.NamedTemporaryFile().name
        cells = []
        code = "print 'hello'"
        cells.append(v4.new_code_cell(source=code))
        nb = v4.new_notebook(cells=cells)
        with open(dummy_nb_file, 'wr') as f:
            write(nb, f, version=4)
        # upload dummy notebook
        with open(dummy_nb_file, 'r') as f:
            fs.put(f.read(), filename="dummy.ipynb")
        nb_list = fs.list()
        expected = ['dummy.ipynb']
        self.assertListEqual(nb_list, expected)
        # upload job notebook
        with open(dummy_nb_file, 'r') as f:
            fs.put(f.read(), filename="job_dummy.ipynb")
        job_list = om.jobs.list()
        expected = ['job_dummy.ipynb']
        self.assertListEqual(job_list, expected)

    def test_job_run_invalid(self):
        om = Omega()
        defaults = omegaml.settings()
        fs = om.jobs.get_fs(defaults.OMEGA_NOTEBOOK_COLLECTION)
        dummy_nb_file = tempfile.NamedTemporaryFile().name
        cells = []
        code = "print 'hello'"
        nb_file = 'job_dummy.ipynb'
        cells.append(v4.new_code_cell(source=code))
        nb = v4.new_notebook(cells=cells)
        with open(dummy_nb_file, 'wr') as f:
            write(nb, f, version=4)
        # upload job notebook
        with open(dummy_nb_file, 'r') as f:
            fs.put(f.read(), filename=nb_file)
        self.assertRaises(ValueError, om.jobs.run_notebook, nb_file)

    def test_job_run_valid(self):
        om = Omega()
        defaults = omegaml.settings()
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
        with open(dummy_nb_file, 'wr') as f:
            write(nb, f, version=4)
        # upload job notebook
        with open(dummy_nb_file, 'r') as f:
            fs.put(f.read(), filename=nb_file)
        result = om.jobs.run_notebook(nb_file)
        self.assertIsInstance(result, Metadata)

    def test_run_nonexistent_job(self):
        om = Omega()
        self.assertRaises(
            gridfs.errors.NoFile, om.jobs.run_notebook, 'dummys.ipynb')

    def test_job_status(self):
        om = Omega()
        defaults = omegaml.settings()
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
        with open(dummy_nb_file, 'wr') as f:
            write(nb, f, version=4)
        # upload job notebook
        with open(dummy_nb_file, 'r') as f:
            fs.put(f.read(), filename=nb_file)
        om.jobs.run_notebook('job_dummy.ipynb')
        expected = Metadata.objects.filter(name='job_dummy.ipynb', kind__in=Metadata.KINDS)
        result = om.jobs.get_status('job_dummy.ipynb')
        self.assertIsInstance(result[0], Metadata)
        self.assertIsInstance(expected[0], Metadata)
