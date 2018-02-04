
from __future__ import absolute_import

import datetime
import os
import re
from uuid import uuid4

from croniter import croniter
from django.conf import settings
import gridfs
from mongoengine.fields import GridFSProxy
from nbformat import read as nbread, write as nbwrite
from nbformat.v4.nbbase import nbformat
from runipy.notebook_runner import NotebookRunner
from six import StringIO, BytesIO
import yaml

from omegaml import signals
from omegaml.documents import Metadata
from omegaml.store import OmegaStore
from omegaml.tasks import run_omegaml_job
from omegaml.util import settings as omega_settings


class OmegaJobs(object):

    """
    Omega Jobs API
    """

    # TODO this class is in serious need for refactoring

    def __init__(self, prefix=None, store=None):
        self.defaults = omega_settings()
        # FIXME should be 'jobs' prefix
        prefix = prefix or 'jobs'
        self.store = store or OmegaStore(prefix=prefix)
        self.kind = Metadata.OMEGAML_JOBS

    @property
    def _db(self):
        return self.store.mongodb

    @property
    def _fs(self):
        return self.store.fs

    def collection(self, name):
        return self.store.collection(name)

    def drop(self, name):
        return self.store.drop(name)

    def metadata(self, name):
        return self.store.metadata(name)

    def put(self, obj, name, attributes=None):
        """
        Store a NotebookNode

        :param obj: the NotebookNode to store
        :param name: the name of the notebook
        """
        sbuf = StringIO()
        bbuf = BytesIO()
        # nbwrite expects string, fs.put expects bytes
        nbwrite(obj, sbuf, version=4)
        sbuf.seek(0)
        bbuf.write(sbuf.getvalue().encode('utf8'))
        bbuf.seek(0)
        # see if we have a file alredy, if so replace the gridfile
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
        meta = self.store.metadata(name)
        if meta:
            try:
                outf = meta.gridfile
            except gridfs.errors.NoFile as e:
                raise e
            # nbwrite wants a string, outf is bytes
            sbuf = StringIO()
            sbuf.write(outf.read().decode('utf8'))
            sbuf.seek(0)
            nb = nbread(sbuf, as_version=4)
            return nb
        else:
            raise gridfs.errors.NoFile(
                ">{0}< does not exist in jobs bucket '{1}'".format(
                    name, self.store.bucket))

    def get_fs(self, collection=None):
        """
        get gridfs instance using url and collection provided
        """
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

    def run(self, nb_file):
        """
        run the notebook on the runtime cluster
        """
        from omegaml.tasks import run_omegaml_job
        result = run_omegaml_job.delay(nb_file)
        signals.job_run.send(sender=None, name=nb_file)
        return result.get()

    def open_notebook(self, nb_filename):
        """
        Reads and returns a notebook
        """
        try:
            # for version 3
            notebook = nbread(open(nb_filename), as_version=3)
        except Exception:
            # for version 4
            notebook = nbread(open(nb_filename), as_version=4)
        except Exception:
            raise ValueError(
                "Notebook {0} do not match any applicable versions!".format(
                    nb_filename))
        return notebook

    def get_notebook_config(self, nb_filename):
        """
        returns the omegaml script config on
        the notebook's first cell
        """
        gfs = self.get_fs()
        try:
            # nb_filename = 'job_'+nb_file+'.ipynb'
            outf = gfs.get_last_version(nb_filename)
            with open(nb_filename, 'wb') as nb_file:
                nb_file.write(outf.read())
        except gridfs.errors.NoFile:
            raise gridfs.errors.NoFile(
                "Notebook {0} does not exist in collection '{1}'".format(
                    nb_filename, self.defaults.OMEGA_NOTEBOOK_COLLECTION))

        notebook = self.open_notebook(nb_filename)
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

    def run_notebook(self, nb_filename):
        """
        run the job immediately.
        the job parameter is the name of the job script as in ipynb.
        Inserts and returns the Metadata document for the job.
        """
        from pycloudfs import S3Helper
        gfs = self.get_fs()
        # FIXME get the notebook from mongo store without storing locally
        config = self.get_notebook_config(nb_filename)
        # nb_filename = 'job_'+nb_file+'.ipynb'
        # FIXME this only works because get_notebook_config stored the file
        # locally
        notebook = self.open_notebook(nb_filename)
        r = NotebookRunner(notebook)
        r.run_notebook(skip_exceptions=True)
        filename, ext = os.path.splitext(nb_filename)
        ts = datetime.datetime.now().strftime('%s')
        result_nb = 'result' + filename.lstrip('job') + '_{0}.ipynb'.format(ts)
        nbwrite(r.nb, open(result_nb, 'w',), version=3)
        # store results
        s3file = {}
        fileid = None
        if config.get('results-store') == 's3':
            AWS_ACCESS_KEY_ID = os.environ.get(
                'AWS_ACCESS_KEY_ID', getattr(
                    settings, 'AWS_ACCESS_KEY_ID'))
            AWS_SECRET_ACCESS_KEY = os.environ.get(
                'AWS_SECRET_ACCESS_KEY', getattr(
                    settings, 'AWS_SECRET_ACCESS_KEY'))
            bucket = os.environ.get('AWS_TEST_BUCKET', 'shrebo')
            path = 'ipynb_results'
            s3 = S3Helper(
                bucket=bucket,
                path=path,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
            s3file = dict(
                bucket=bucket,
                prefix=path,
                name=result_nb)
            s3.upload_file(result_nb)
        if config.get('results-store') == 'gridfs':
            with open(result_nb, 'rb') as fin:
                fileid = gfs.put(fin, filename=os.path.basename(result_nb))
        os.remove(result_nb) if os.path.isfile(result_nb) else None
        # shutdown the ipython kernel
        r.shutdown_kernel()
        # check if this job was scheduled earlier
        try:
            metadata = Metadata.objects.get(
                name=nb_filename, kind=Metadata.OMEGAML_RUNNING_JOBS)
            metadata.gridfile = GridFSProxy(
                grid_id=fileid,
                collection_name=self.defaults.OMEGA_NOTEBOOK_COLLECTION)
            metadata.attributes['state'] = 'EXECUTED'
            metadata.s3file = s3file
            metadata.save()
            # FIXME return only at function end, same below
            return metadata
        except Metadata.DoesNotExist:
            attrs = {}
            attrs['config'] = config
            attrs['state'] = 'EXECUTED'
            return Metadata(
                name=nb_filename,
                kind=Metadata.OMEGAML_RUNNING_JOBS,
                s3file=s3file,
                gridfile=GridFSProxy(
                    grid_id=fileid,
                    collection_name=self.defaults.OMEGA_NOTEBOOK_COLLECTION),
                attributes=attrs).save()

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
        from omegaml.tasks import schedule_omegaml_job
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
        signals.job_schedule.send(sender=None, name=nb_file)
        return result

    def get_status(self, job):
        """
        returns list of Metadata objects for this job
        """
        # FIXME this should use the store.metadata
        return Metadata.objects.filter(name=job, kind__in=Metadata.KINDS)

    def get_result(self, job):
        """
        returns the result gridfile object for the respective Metadata
        """
        fs = self.get_fs(self.defaults.OMEGA_NOTEBOOK_COLLECTION)
        if isinstance(job, Metadata):
            return fs.get(job.gridfile.grid_id)

        try:
            metadata = Metadata.objects.order_by(
                '-created').filter(name=job).first()
            if not metadata:
                raise Metadata.DoesNotExist
            return fs.get(metadata.gridfile.grid_id)
        except Metadata.DoesNotExist:
            try:
                collection = self.get_collection('metadata')
                doc = collection.find_one({'attributes.task_id': job})
                metadata = Metadata.objects.get(gridfile=doc.get('gridfile'))
                if not metadata:
                    raise Exception
                return fs.get(metadata.gridfile.grid_id)
            except Exception:
                raise Metadata.DoesNotExist(
                    'No job found related to the name or task id: {0}'.format(job))
