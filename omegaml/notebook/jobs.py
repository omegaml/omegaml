from __future__ import absolute_import

import datetime
import re
from uuid import uuid4

import gridfs
import yaml
from croniter import croniter
from mongoengine.fields import GridFSProxy
from nbconvert.preprocessors.execute import ExecutePreprocessor
from nbformat import read as nbread, write as nbwrite, v4 as nbv4
from six import StringIO, BytesIO

from omegaml.documents import Metadata
from omegaml.notebook.tasks import run_omegaml_job
from omegaml.store import OmegaStore
from omegaml.util import settings as omega_settings


class OmegaJobs(object):
    """
    Omega Jobs API
    """

    # TODO this class should be a proper backend class

    def __init__(self, prefix=None, store=None, defaults=None):
        self.defaults = defaults or omega_settings()
        prefix = prefix or 'jobs'
        self.store = store or OmegaStore(prefix=prefix)
        self.kind = Metadata.OMEGAML_JOBS

    def __repr__(self):
        return 'OmegaJobs(store={})'.format(self.store.__repr__())

    @property
    def _db(self):
        return self.store.mongodb

    @property
    def _fs(self):
        return self.store.fs

    def collection(self, name):
        if not name.endswith('.ipynb'):
            name += '.ipynb'
        return self.store.collection(name)

    def drop(self, name):
        if not name.endswith('.ipynb'):
            name += '.ipynb'
        return self.store.drop(name)

    def metadata(self, name):
        if not name.endswith('.ipynb'):
            name += '.ipynb'
        return self.store.metadata(name)

    def exists(self, name):
        if not name.endswith('.ipynb'):
            name += '.ipynb'
        return len(self.store.list(name)) > 0

    def put(self, obj, name, attributes=None):
        """
        Store a NotebookNode

        :param obj: the NotebookNode to store
        :param name: the name of the notebook
        """
        if not name.endswith('.ipynb'):
            name += '.ipynb'
        sbuf = StringIO()
        bbuf = BytesIO()
        # nbwrite expects string, fs.put expects bytes
        nbwrite(obj, sbuf, version=4)
        sbuf.seek(0)
        bbuf.write(sbuf.getvalue().encode('utf8'))
        bbuf.seek(0)
        # see if we have a file already, if so replace the gridfile
        meta = self.store.metadata(name)
        if not meta:
            filename = uuid4().hex
            fileid = self._fs.put(bbuf, filename=filename)
            meta = self.store._make_metadata(name=name,
                                             prefix=self.store.prefix,
                                             bucket=self.store.bucket,
                                             kind=self.kind,
                                             attributes=attributes,
                                             gridfile=GridFSProxy(grid_id=fileid))
        else:
            meta.gridfile.replace(bbuf)
        return meta.save()

    def get(self, name):
        """
        Retrieve a notebook and return a NotebookNode
        """
        if not name.endswith('.ipynb'):
            name += '.ipynb'
        meta = self.store.metadata(name)
        if meta:
            try:
                outf = meta.gridfile
            except gridfs.errors.NoFile as e:
                raise e
            # nbwrite wants a string, outf is bytes
            sbuf = StringIO()
            data = outf.read()
            if data is None:
                msg = 'Expected content in {name}, got None'.format(**locals())
                raise ValueError(msg)
            sbuf.write(data.decode('utf8'))
            sbuf.seek(0)
            nb = nbread(sbuf, as_version=4)
            return nb
        else:
            raise gridfs.errors.NoFile(
                ">{0}< does not exist in jobs bucket '{1}'".format(
                    name, self.store.bucket))

    def create(self, code, name):
        """
        create a notebook from code

        :param code: the code as a string
        :param name: the name of the job to create
        :return: the metadata object created
        """
        cells = []
        cells.append(nbv4.new_code_cell(source=code))
        notebook = nbv4.new_notebook(cells=cells)
        # put the notebook
        meta = self.put(notebook, 'testjob')
        return meta

    def get_fs(self, collection=None):
        # legacy support
        return self._fs

    def get_collection(self, collection):
        """
        returns the collection object
        """
        # FIXME this should use store.collection
        return getattr(self.store.mongodb, collection)

    def list(self, jobfilter='.*', raw=False):
        """
        list all jobs matching filter.
        filter is a regex on the name of the ipynb entry.
        The default is all, i.e. `.*`
        """
        job_list = self.store.list(regexp=jobfilter, raw=raw)
        return job_list

    def get_notebook_config(self, nb_filename):
        """
        returns the omegaml script config on
        the notebook's first cell
        """
        notebook = self.get(nb_filename)
        config_cell = notebook.get('worksheets')[0].get('cells')[0]
        yaml_conf = '\n'.join(
            [re.sub('#', '', x, 1) for x in str(
                config_cell.input).splitlines()])
        try:
            yaml_conf = yaml.load(yaml_conf)
            # even a comment qualifies as a valid yaml
            # so testing to check if the yaml is exactly what we expect
            if yaml_conf.get("omegaml.script") is not None:
                pass
            else:
                raise ValueError(
                    'Notebook configuration either not present or has errors!')
        except Exception:
            raise ValueError(
                'Notebook configuration either not present or has errors!')

        return yaml_conf.get("omegaml.script")

    def run(self, name):
        """
        Run a job immediately

        The job is run and the results are stored in the given filename

        :param name: the name of the jobfile
        :return: the metadata of the job
        """
        return self.run_notebook(name)

    def run_notebook(self, name):
        """
        run a given notebook immediately.
        the job parameter is the name of the job script as in ipynb.
        Inserts and returns the Metadata document for the job.
        """
        notebook = self.get(name)
        meta_job = self.metadata(name)
        ts = datetime.datetime.now().strftime('%s')
        # execute
        try:
            ep = ExecutePreprocessor()
            ep.preprocess(notebook, {'metadata': {'path': '/'}})
        except Exception as e:
            status = str(e)
        else:
            status = 'OK'
            # record results
            meta_results = self.put(
                notebook, 'results/{name}_{ts}'.format(**locals()))
            meta_results.attributes['source_job'] = name
            meta_results.save()
            job_results = meta_job.attributes.get('job_results', [])
            job_results.append(meta_results.name)
            meta_job.attributes['job_results'] = job_results
        # record final job status
        job_runs = meta_job.attributes.get('job_runs', {})
        job_runs[ts] = status
        meta_job.attributes['job_runs'] = job_runs
        meta_job.save()
        return meta_job

    def schedule(self, nb_file):
        """
        Schedule a processing of a notebook as per the interval
        specified on the job script
        """
        # FIXME this looks somewhat unstable. currently we schedule by
        #       inserting metadata that sets the state of the job to
        #       RECEIVED. Then the task execute_script which is
        #       scheduled by celery gets all new jobs not yet in RECEIVED
        #       state, and schedules for the next iteration. What happens
        #       if a job was scheduled already how will it get reschduled?
        attrs = {}
        config = self.get_notebook_config(nb_file)
        now = datetime.datetime.now()
        interval = config.get('run-at')
        iter_next = croniter(interval, now)
        run_at = iter_next.get_next(datetime.datetime)
        next_run_time = iter_next.get_next(datetime.datetime)
        kwargs = dict(
            config=config,
            run_at=run_at,
            next_run_time=next_run_time)
        # check if this job was scheduled earlier
        try:
            metadata = Metadata.objects.get(
                name=nb_file, kind=Metadata.OMEGAML_RUNNING_JOBS)
            if metadata.attributes.get('state') == "RECEIVED":
                # FIXME return only at end of method.
                return metadata.attributes.get('task_id')
        except Metadata.DoesNotExist:
            # set attributes
            attrs['config'] = config
            attrs['next_run_time'] = run_at
            attrs['state'] = 'RECEIVED'
            Metadata(
                name=nb_file,
                kind=Metadata.OMEGAML_RUNNING_JOBS,
                attributes=attrs).save()
        result = run_omegaml_job.apply_async(
            args=[nb_file], eta=run_at, kwargs=kwargs)
        return result
