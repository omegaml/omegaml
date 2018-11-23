from __future__ import absolute_import

import os

import gridfs
from nbformat import v4

from omegaml import Omega
from omegaml.documents import Metadata
from omegaml.tests.test_jobs import JobTests
from omegaml.util import settings as omegaml_settings


class EnterpriseJobTests(JobTests):
    @property
    def om(self):
        om = Omega()
        return om

    def test_export_job_html(self):
        """
        test export a job to HTML
        """
        fs = self.fs
        om = self.om
        # create a notebook
        cells = []
        code = "print('hello')"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put and run the notebook
        meta = om.jobs.put(notebook, 'testjob-html')
        om.jobs.run('testjob-html')
        # get results and output
        meta = om.jobs.metadata('testjob-html')
        resultnb_name = meta.attributes['job_results'][0]
        outpath = '/tmp/test.html'
        om.jobs.export(resultnb_name, outpath)
        self.assertTrue(os.path.exists(outpath))

    def test_export_job_slides(self):
        """
        test export a job to slides HTML (reveal.js)
        """
        fs = self.fs
        om = self.om
        # create a notebook with slides
        # see https://github.com/jupyter/nbconvert/blob/master/nbconvert/templates/html/slides_reveal.tpl#L1:14
        cells = []
        code = "print('slide 1')"
        cells.append(v4.new_markdown_cell('Slide 1', metadata=dict(slide_start=True)))
        cells.append(v4.new_code_cell(source=code))
        cells.append(v4.new_markdown_cell('***', metadata=dict(slide_end=True)))
        code = "print('slide 2')"
        cells.append(v4.new_markdown_cell('Slide 2', metadata=dict(slide_start=True)))
        cells.append(v4.new_code_cell(source=code))
        cells.append(v4.new_markdown_cell('***', metadata=dict(slide_end=True)))
        notebook = v4.new_notebook(cells=cells)
        # put and run the notebook
        meta = om.jobs.put(notebook, 'testjob-html')
        om.jobs.run('testjob-html')
        # get results and output
        meta = om.jobs.metadata('testjob-html')
        resultnb_name = meta.attributes['job_results'][0]
        outpath = '/tmp/test.html'
        om.jobs.export(resultnb_name, outpath, format='slides')
        self.assertTrue(os.path.exists(outpath))

    def test_export_job_pdf(self):
        """
        test export a job to PDF
        """
        fs = self.fs
        om = self.om
        # create a notebook
        cells = []
        code = "print('hello')"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put and run the notebook
        meta = om.jobs.put(notebook, 'testjobx')
        om.jobs.run('testjobx')
        # get results and output
        meta = om.jobs.metadata('testjobx')
        resultnb_name = meta.attributes['job_results'][0]
        outpath = '/tmp/test.pdf'
        om.jobs.export(resultnb_name, outpath, 'pdf')
        self.assertTrue(os.path.exists(outpath))

    def old_test_job_run_valid(self):
        om = Omega()
        defaults = omegaml_settings()
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
        om.jobs.put(nb, nb_file)
        result = om.jobs.run_notebook(nb_file)
        self.assertIsInstance(result, Metadata)

    def test_run_nonexistent_job(self):
        om = self.om
        self.assertRaises(
            gridfs.errors.NoFile, om.jobs.run_notebook, 'dummys.ipynb')
