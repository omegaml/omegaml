import os

from behave import given, then, when

from omegaml.tests.features.util import get_admin_secrets


@given('we have a connection to omegaml')
def connection(ctx):
    import omegaml as om
    ctx.feature.om = om.setup()
    assert ctx.feature.om is not None


@when('we ingest data')
def ingest(ctx):
    import pandas as pd
    om = ctx.feature.om
    data = {
        'x': range(10),
    }
    df = pd.DataFrame(data)
    df['y'] = df['x'] * 2
    om.datasets.put(df, 'sample', append=False)
    assert 'sample' in om.datasets.list()


@when('we build a model')
def model(ctx):
    from sklearn.linear_model import LinearRegression
    om = ctx.feature.om
    reg = LinearRegression()
    om.models.put(reg, 'regmodel')
    resp = om.runtime.model('regmodel').fit('sample[x]', 'sample[y]')
    resp.get()


@then('we can predict a result')
def predict(ctx):
    import numpy as np
    om = ctx.feature.om
    resp = om.runtime.model('regmodel').predict([1])
    result = resp.get()
    assert np.isclose(result[0], 2), "expected approx. 2, got {}".format(result[0])
    resp = om.runtime.model('regmodel').predict([50])
    result = resp.get()
    assert np.isclose(result[0], 100), "expected approx. 100, got {}".format(result[0])


@when('we store {scope} credentials in {dataset}')
def store_secrets(ctx, scope, dataset):
    om = ctx.feature.om
    secrets = get_admin_secrets(scope)
    om.datasets.put(secrets, dataset, append=False)
    assert 'secrets' in om.datasets.list()


@when('we save the {nbname} notebook')
def store_tutorial_notebook(ctx, nbname):
    om = ctx.feature.om
    nbfname = os.path.join(ctx.nbfiles, '{nbname}.ipynb'.format(**locals()))
    meta = om.jobs.put(nbfname, nbname, replace=True, kind='script.ipynb')
    assert meta.name == f'{nbname}.ipynb'
    assert meta.kind == 'script.ipynb'
