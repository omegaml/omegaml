
import omegaml
from omegaml.documents import Metadata
from omegaml.store import OmegaStore
import datetime
from runipy.notebook_runner import NotebookRunner
from mongoengine.fields import GridFSProxy
from croniter import croniter
import re
import yaml
import os
import gridfs
from nbformat import read, write


class OmegaJobs(object):
    """
    Omega Jobs API
    """
    def __init__(self):
        self.defaults = omegaml.settings()
        self.store = OmegaStore(prefix=None)
        self._db = self.store.mongodb

    def get_fs(self, collection=None):
        """
        get gridfs instance using url and collection provided
        """
        if collection is None:
            collection = self.defaults.OMEGA_NOTEBOOK_COLLECTION

        try:
            self._fs = gridfs.GridFS(self.store.mongodb, collection)
        except Exception as e:
            raise e

        return self._fs

    def get_collection(self, collection):
        """
        returns the collection object
        """
        return getattr(self.store.mongodb, collection)

    def list(self, jobfilter='.*'):
        """
        list all jobs matching filter.
        filter is a regex on the name of the ipynb entry.
        The default is all, i.e. `.*`
        """
        gfs = self.get_fs()
        file_list = gfs.list()
        job_list = [job for job in file_list if job.startswith(
            'job_') and job.endswith('.ipynb') and re.search(jobfilter, job)]
        return job_list

    def run(self, nb_file):
        """
        run the notebook using a celery task
        """
        from omegaml.tasks import run_omegaml_job
        result = run_omegaml_job.delay(nb_file)
        return result.get()

    def open_notebook(self, nb_filename):
        try:
            # for version 3
            notebook = read(open(nb_filename), as_version=3)
        except Exception:
            # for version 4
            notebook = read(open(nb_filename), as_version=4)
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
            with open(nb_filename, 'w') as nb_file:
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
                raise ValueError('Notebook configuration either not present \
                    or has errors!')
        except Exception:
            raise ValueError('Notebook configuration either not present \
                or has errors!')

        return yaml_conf.get("omegaml.script")

    def run_notebook(self, nb_filename):
        """
        run the job immediately.
        the job parameter is the name of the job script as in ipynb.
        Inserts and returns the Metadata document for the job.
        """
        gfs = self.get_fs()
        config = self.get_notebook_config(nb_filename)
        # nb_filename = 'job_'+nb_file+'.ipynb'
        notebook = self.open_notebook(nb_filename)
        r = NotebookRunner(notebook)
        r.run_notebook(skip_exceptions=True)
        filename, ext = os.path.splitext(nb_filename)
        ts = datetime.datetime.now().strftime('%s')
        result_nb = 'result'+filename.lstrip('job')+'_{0}.ipynb'.format(ts)
        write(r.nb, open(result_nb, 'w',), version=3)
        # store results
        # if config.get('results-store') == 's3':
        #     bucket = os.environ.get('AWS_TEST_BUCKET', 'shrebo')
        #     s3 = S3Helper(bucket=bucket, path='ipynb_results')
        #     s3.upload_file(result_nb)
        if config.get('results-store') == 'gridfs':
            fileid = gfs.put(open(
                result_nb, 'r'), filename=os.path.basename(result_nb))
        os.remove(result_nb) if os.path.isfile(result_nb) else None
        # check if this job was scheduled earlier
        try:
            metadata = Metadata.objects.get(
                name=nb_filename, kind=Metadata.OMEGAML_RUNNING_JOBS)
            metadata.gridfile = GridFSProxy(
                grid_id=fileid,
                collection_name=self.defaults.OMEGA_NOTEBOOK_COLLECTION)
            metadata.save()
            return metadata
        except Metadata.DoesNotExist:
            attrs = {}
            attrs['config'] = config
            return Metadata(
                name=nb_filename,
                kind=Metadata.OMEGAML_RUNNING_JOBS,
                gridfile=GridFSProxy(
                    grid_id=fileid,
                    collection_name=self.defaults.OMEGA_NOTEBOOK_COLLECTION),
                attributes=attrs).save()

    def schedule(self, nb_file):
        """
        Schedule a processing of a notebook as per the interval
        specified on the job script
        """
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
        return schedule_omegaml_job.apply_async(
            args=[nb_file], eta=run_at, kwargs=kwargs)

    def get_status(self, job):
        """
        returns list of Metadata objects for this job
        """
        return Metadata.objects.filter(name=job, kind__in=Metadata.KINDS)

    def get_result(self, job):
        """
        returns the result gridfile object for the respective Metadata
        """
        if isinstance(job, Metadata):
            return Metadata.gridfile

        try:
            metadata = Metadata.objects.filter(name=job)
            if not metadata:
                raise Metadata.DoesNotExist
            return metadata[0].gridfile
        except Metadata.DoesNotExist:
            try:
                collection = self.get_collection('metadata')
                metadata = collection.find_one({'attributes.task_id': job})
                if not metadata:
                    raise Exception
                return Metadata.objects.get(
                    gridfile=metadata.get('gridfile')).gridfile
            except Exception:
                raise Metadata.DoesNotExist('No job found related to the name or task id: {0}'.format(job))
