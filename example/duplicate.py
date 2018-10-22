#!/usr/bin/env python
"""
example program to run in ipython
"""
# train a model to learn to duplicate numbers
from __future__ import absolute_import
from __future__ import print_function
import pandas as pd
import numpy as np
import os
from omegaml import Omega
from sklearn.linear_model import LinearRegression
from omegaml.util import override_settings
import argparse
from six.moves import range


def testOmegaml(
        broker_url,
        queue,
        exchange,
        mongo_url,
        collection):
    # make sure to set accordingly
    override_settings(
        OMEGA_BROKER=broker_url,
        OMEGA_CELERY_DEFAULT_QUEUE=queue,
        OMEGA_CELERY_DEFAULT_EXCHANGE=exchange,
        OMEGA_MONGO_URL=mongo_url,
        OMEGA_MONGO_COLLECTION=collection
    )

    om = Omega()
    om.runtime.celeryapp.conf.CELERY_ALWAYS_EAGER = False
    os.environ['DJANGO_SETTINGS_MODULE'] = ''

    # create a data frame with x, y
    x = np.array(list(range(10, 20)))
    y = x * 2
    df = pd.DataFrame(dict(x=x, y=y))

    # prepare and store data for training the model
    X = df[['x']]
    Y = df[['y']]
    om.datasets.put(X, 'datax')
    om.datasets.put(Y, 'datay')

    # fit locally and store model for comparison
    lr = LinearRegression()
    lr.fit(X, Y)
    pred = lr.predict(X)
    om.models.put(lr, 'duplicate')

    # train remotely
    result = om.runtime.model('duplicate').fit('datax', 'datay')
    result.get()

    # check the model actually works
    # -- using the data on the server
    result = om.runtime.model('duplicate').predict('datax')
    pred1 = result.get()
    # -- using local data
    new_x = np.random.randint(0, 100, 10).reshape(10, 1)
    result = om.runtime.model('duplicate').predict(new_x)
    pred2 = result.get()

    # use np.allclose in case we have floats
    assert np.allclose(pred, pred1), "oh snap, something went wrong! %s != %s" % (pred, pred1)
    assert np.allclose(new_x * 2, pred2), "oh snap, something went wrong! %s != %s" % (pred2, new_x * 2)

    print("nice, everything works. thank you very much")
    df1 = pd.DataFrame(dict(asked=X.x, result=pred1.flatten()), index=list(range(0, len(X))))
    df2 = pd.DataFrame(dict(asked=new_x.flatten(), result=pred2.flatten()), index=list(range(0, len(X))))
    result = om.runtime.model('duplicate').predict([[5]])
    pred2 = result.get()

    pd.concat([df1, df2]).sort_values(by='asked')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--broker-url", action="store", help="celery broker url", required=True)
    parser.add_argument("--queue", action="store", help="celery queue", required=True)
    parser.add_argument("--exchange", action="store", help="celery exchange", required=True)
    parser.add_argument("--mongo-url", action="store", help="Mongo url",  required=True)
    parser.add_argument("--collection", action="store", help="Mongo collection", required=True)
    args = parser.parse_args()
    testOmegaml(**vars(args))
