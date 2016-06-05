import os

from celery import shared_task
from celery import Task

from omegaml import Omega
from omegaml.jobs import OmegaJobs
from omegaml.documents import Metadata


class NotebookTask(Task):
    abstract = True

    def __init__(self, *args, **kwargs):
        jobs = OmegaJobs()
        self.collection = getattr(jobs.store.mongodb, 'omegaml_nbstatus')

    def on_success(self, retval, task_id, *args, **kwargs):
        nbfile, config, last_runtime, next_runtime = args[0][0:4]
        nb_status_data = {
            "task_id": task_id,
            "last_runtime": last_runtime,
            "next_runtime": next_runtime,
            "state": "SUCCESS",
        }
        self.collection.update_one({
            "_id": nbfile
            }, {
            '$set': nb_status_data
            }, upsert=True)

    def on_failure(self, retval, task_id, *args, **kwargs):
        nbfile, config, last_runtime, next_runtime = args[0][0:4]
        nb_status_data = {
            "task_id": task_id,
            "last_runtime": last_runtime,
            "next_runtime": next_runtime,
            "state": "FAILURE",
        }
        self.collection.update_one({
            "_id": nbfile
            }, {
            '$set': nb_status_data
            }, upsert=True)


@shared_task
def omega_predict(modelname, Xname, rName=None, pure_python=True, **kwargs):
    om = Omega()
    model = om.models.get(modelname)
    data, meta = get_data(om, Xname)
    result = model.predict(data, **kwargs)
    if pure_python:
        result = result.tolist()
    if rName:
        meta = om.put(result, rName)
        result = meta
    return result


@shared_task
def omega_predict_proba(modelname, Xname, rName=None, pure_python=True,
                        **kwargs):
    om = Omega()
    model = om.models.get(modelname)
    data, meta = get_data(om, Xname)
    result = model.predict_proba(data, **kwargs)
    if pure_python:
        result = result.tolist()
    if rName:
        om.put(result, rName)
        result = meta
    return result


@shared_task
def omega_fit(modelname, Xname, Yname=None, pure_python=True, **kwargs):
    om = Omega()
    model = om.models.get(modelname)
    X, metaX = get_data(om, Xname)
    Y, metaY = None, None
    if Yname:
        Y, metaY = get_data(om, Yname)
    result = model.fit(X, Y, **kwargs)
    # store information required for retraining
    model_attrs = {
        'metaX': metaX.to_mongo(),
        'metaY': metaY.to_mongo() if metaY is not None else None,
    }
    try:
        import sklearn
        model_attrs['scikit-learn'] = sklearn.__version__
    except:
        model_attrs['scikit-learn'] = 'unknown'
    om.models.put(model, modelname, attributes=model_attrs)
    if pure_python:
        result = '%s' % result
    return result


@shared_task
def omega_score(modelname, Xname, Yname, rName=True, pure_python=True,
                **kwargs):
    om = Omega()
    model = om.models.get(modelname)
    X, _ = get_data(om, Xname)
    Y, _ = get_data(om, Yname)
    result = model.score(X, Y, **kwargs)
    if rName:
        meta = om.put(result, rName)
        result = meta
    return result


@shared_task
def omega_fit_transform(modelname, Xname, Yname=None, rName=None,
                        pure_python=True, **kwargs):
    om = Omega()
    model = om.models.get(modelname)
    X, metaX = get_data(om, Xname)
    Y, metaY = None, None
    if Yname:
        Y, metaY = get_data(om, Yname)
    result = model.fit_transform(X, Y, **kwargs)
    # store information required for retraining
    model_attrs = {
        'metaX': metaX.to_mongo(),
        'metaY': metaY.to_mongo() if metaY is not None else None
    }
    try:
        import sklearn
        model_attrs['scikit-learn'] = sklearn.__version__
    except:
        model_attrs['scikit-learn'] = 'unknown'
    om.models.put(model, modelname, attributes=model_attrs)
    if rName:
        om.put(result, rName)
    return result


@shared_task
def omega_transform(modelname, Xname, rName=None, **kwargs):
    om = Omega()
    model = om.models.get(modelname)
    X, _ = get_data(om, Xname)
    result = model.transform(X, **kwargs)
    if rName:
        meta = om.put(result, rName)
        result = meta
    return result


@shared_task
def omega_settings():
    if os.environ.get('OMEGA_DEBUG'):
        from omegaml.util import settings
        defaults = settings()
        return {k: getattr(defaults, k, '')
                for k in dir(defaults) if k and k.isupper()}
    return {'error': 'settings dump is disabled'}


def get_data(om, name):
    data = om.datasets.get(name)
    meta = om.datasets.meta_for(name)
    if meta.kind == Metadata.PYTHON_DATA:
        # we can only use one python object at a time
        return data[0], meta
    return data, meta


@shared_task
def run_omegaml_job(nb_file):
    """
    retrieves the notebook from gridfs and runs it
    """
    om = Omega()
    result = om.jobs.run_notebook(nb_file)
    return result


@shared_task(base=NotebookTask)
def schedule_omegaml_job(nb_file, config, run_at=None, next_run_time=None):
    """
    retrieves the notebook from gridfs and runs it
    """
    om = Omega()
    result = om.jobs.run_notebook(nb_file)
    return result
