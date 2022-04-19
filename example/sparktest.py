#!/usr/bin/env python
"""
example program to run in ipython
"""
# train a model to learn to duplicate numbers
from __future__ import absolute_import
from __future__ import print_function

from io import StringIO

import pandas as pd
import numpy as np
import os
from omegaml import Omega
from omegaml.util import override_settings, get_labeledpoints
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
    x = np.array(list(range(10, 20)))
    y = x * 2

    data = """
    label,legs,wings,sound
    0,4,0,1
    0,4,0,2
    0,2,1,3
    1,2,1,4
    """

    test_data = """
    label,legs,wings,sound
    0,4,0,1
    0,4,0,2
    0,2,1,3
    1,2,1,4
    0,2,1,3
    0,4,0,2
    1,2,1,4
    """

    infile_orig = StringIO(data)
    infile_test = StringIO(test_data)
    df_orig = pd.read_csv(infile_orig)
    df_test = pd.read_csv(infile_test)
    df_array = pd.DataFrame(dict(x=x, y=y))

    # create and store spark KMeans model
    om.models.put(
        'pyspark.mllib.clustering.KMeans',
        'sparktest', params=dict(k=10))
    om.models.put(
        'pyspark.mllib.classification.LogisticRegressionWithLBFGS',
        'sparklogictest')

    # prepare and store data for training the model
    X_arr = df_array[['x']]
    Y_arr = df_array[['y']]
    om.datasets.put(X_arr, 'spark_datax')
    om.datasets.put(Y_arr, 'spark_datay')
    om.datasets.put(df_orig, 'logic_orig')

    # split test data in multiple dfs
    om.datasets.put(pd.DataFrame(
        df_test[df_test.columns[0]]), 'logic_test_labels')
    om.datasets.put(pd.DataFrame(
        df_test[df_test.columns[1:]]), 'logic_test_features')

    # train & store trained model using spark
    result = om.runtime.model('sparktest').fit('spark_datax')
    result.get()

    # check the model actually works
    # -- using the data on the server
    result = om.runtime.model('sparktest').predict('spark_datay')
    pred1 = result.get()

    # use np.allclose in case we have floats
    assert len(pred1.index) == len(df_array.index), "oh snap, something went wrong! %s != %s" % (len(pred1.index), len(df_array.index))
    print("===========================")
    print("Spark KMeans test succeeded")
    print("===========================")
    # get labeled point to use for logistic regression test
    result = om.runtime.model('sparklogictest').fit('logic_orig')
    pred2 = result.get()

    labeled_point_test = get_labeledpoints(
        'logic_test_features', 'logic_test_labels')
    labels_and_preds = labeled_point_test.map(
        lambda pred: (pred.label, pred2.predict(pred.features)))
    accuracy_test = labels_and_preds.filter(
        lambda v_p: v_p[0] == v_p[1]).count() / float(labeled_point_test.count())

    assert accuracy_test >= 0.75, "not ok, %s" % (accuracy_test)

    prediction = [
        'animal' if lp[1] == 0 else 'plane'
        for lp in labels_and_preds.toLocalIterator()]
    print("Here's what I think", prediction)
    print("===========================")
    print("LogisticRegressionWithLBFGS test succeeded")
    print("===========================")
    print("nice, everything works. thank you very much")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--broker-url", action="store", help="celery broker url", required=True)
    parser.add_argument("--queue", action="store", help="celery queue", required=True)
    parser.add_argument("--exchange", action="store", help="celery exchange", required=True)
    parser.add_argument("--mongo-url", action="store", help="Mongo url",  required=True)
    parser.add_argument("--collection", action="store", help="Mongo collection", required=True)
    args = parser.parse_args()
    testOmegaml(**vars(args))
