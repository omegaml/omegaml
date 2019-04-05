from behave import given, when, then


@given('we have a connection to omegaml')
def connection(ctx):
    import omegaml as om
    ctx.om = om.setup()
    assert ctx.om is not None

@when('we ingest data')
def ingest(ctx):
    import pandas as pd
    om = ctx.om
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
    om = ctx.om
    reg = LinearRegression()
    om.models.put(reg, 'regmodel')
    om.runtime.model('regmodel').fit('sample[x]', 'sample[y]')

@then('we can predict a result')
def predict(ctx):
    import numpy as np
    om = ctx.om
    resp= om.runtime.model('regmodel').predict([1])
    result = resp.get()
    assert np.isclose(result[0], 2), "expected approx. 2, got {}".format(result[0])
    resp = om.runtime.model('regmodel').predict([50])
    result = resp.get()
    assert np.isclose(result[0], 100), "expected approx. 100, got {}".format(result[0])

