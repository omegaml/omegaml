#!/usr/bin/env python
"""
example program to run in ipython
"""
# train a model to learn to duplicate numbers
import pandas as pd
import numpy as np
import os
from omegaml import Omega
from omegaml.util import override_settings
import argparse


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
    x = np.array(range(10, 20))
    y = x * 2
    df = pd.DataFrame(dict(x=x, y=y))

    # create and store spark KMeans model
    om.models.put('pyspark.mllib.clustering.KMeans', 'sparktest')

    # prepare and store data for training the model
    X = df[['x']]
    Y = df[['y']]
    om.datasets.put(X, 'spark_datax')
    om.datasets.put(Y, 'spark_datay')

    # train & store trained model using spark
    om.runtime.model('sparktest').fit('spark_datax')

    # check the model actually works
    # -- using the data on the server
    result = om.runtime.model('sparktest').predict('spark_datay')
    pred1 = result.get()

    # use np.allclose in case we have floats
    assert len(pred1.index) == len(df.index), "oh snap, something went wrong! %s != %s" % (len(pred1.index), len(df.index))

    print "nice, everything works. thank you very much"


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--broker-url", action="store", help="celery broker url", required=True)
    parser.add_argument("--queue", action="store", help="celery queue", required=True)
    parser.add_argument("--exchange", action="store", help="celery exchange", required=True)
    parser.add_argument("--mongo-url", action="store", help="Mongo url",  required=True)
    parser.add_argument("--collection", action="store", help="Mongo collection", required=True)
    args = parser.parse_args()
    testOmegaml(**vars(args))
