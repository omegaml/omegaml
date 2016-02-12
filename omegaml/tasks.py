from celery import shared_task

from omega import Omega

@shared_task
def omega_predict(modelname, Xname):
    om = Omega()
    model = om.models.get(modelname)
    data = om.datasets.get(Xname)
    result = model.predict(data)
    return result

@shared_task
def omega_fit(modelname, Xname, Yname):
    om = Omega()
    model = om.models.get(modelname)
    X = om.datasets.get(Xname)
    Y = om.datasets.get(Yname)
    result = model.fit(X, Y)
    om.models.put(model, modelname)
    return result