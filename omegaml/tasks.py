from celery import shared_task

from omegaml import Omega
from omegaml.documents import Metadata


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


def get_data(om, name):
    data = om.datasets.get(name)
    meta = om.datasets.meta_for(name)
    if meta.kind == Metadata.PYTHON_DATA:
        # we can only use one python object at a time
        return data[0], meta
    return data, meta
