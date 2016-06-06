

from unittest import TestCase
import omegaml
from omegaml import Omega
import tempfile
import gridfs

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
        from nbformat import write, v4
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

    # def test_invalid_job_run(self):
    #     from nbformat import write, v4
    #     om = Omega()
    #     defaults = omegaml.settings()
    #     fs = om.jobs.get_fs(defaults.OMEGA_NOTEBOOK_COLLECTION)
    #     dummy_nb_file = tempfile.NamedTemporaryFile().name
    #     cells = []
    #     code = "print 'hello'"
    #     cells.append(v4.new_code_cell(source=code))
    #     nb = v4.new_notebook(cells=cells)
    #     with open(dummy_nb_file, 'wr') as f:
    #         write(nb, f, version=4)
    #     # upload job notebook
    #     with open(dummy_nb_file, 'r') as f:
    #         fs.put(f.read(), filename="job_dummy.ipynb")
    #     result = om.jobs.run('job_dummy.ipynb')

    #     input_params = """
    #     # omegaml.script:
    #     #   run-at: "*/5 * * * *"
    #     #   results-store: gridfs
    #     #   author: exsys@nixify.com
    #     #   name: Gaurav Ghimire
    #     """
    #     cells.append(v4.new_code_cell(source=input_params))
    #     nb = v4.new_notebook(cells=cells)
    #     with open(dummy_nb_file, 'wr') as f:
    #         write(nb, f, version=4)
    #     # upload dummy notebook
    #     with open(dummy_nb_file, 'r') as f:
    #         fs.put(f.read(), filename="dummy.ipynb")



    # def test_run_nonexistent_job(self):
    #     om = Omega()
    #     self.assertRaises(gridfs.errors.NoFile, om.jobs.run, 'dummys.ipynb')

    # def test_run_existent_job(self):
    #     om = Omega()
    #     result = om.jobs.run('dummys.ipynb')
