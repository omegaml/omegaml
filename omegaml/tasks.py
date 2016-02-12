from celery import shared_task

from omegaml import Omega
from omegaml.documents import Metadata


@shared_task
def omega_predict(modelname, Xname, pure_python=True):
    om = Omega()
    model = om.models.get(modelname)
    data = get_data(om, Xname)
    result = model.predict(data)
    if pure_python:
        result = result.tolist()
    return result


@shared_task
def omega_fit(modelname, Xname, Yname, pure_python=True):
    om = Omega()
    model = om.models.get(modelname)
    X = get_data(om, Xname)
    Y = get_data(om, Yname)
    result = model.fit(X, Y)
    om.models.put(model, modelname)
    if pure_python:
        result = '%s' % result
    return result


def get_data(om, name):
    data = om.datasets.get(name)
    meta = om.datasets.meta_for(name)[0]
    if meta.kind == Metadata.PYTHON_DATA:
        # we can only use one python object at a time
        return data[0]
    return data
