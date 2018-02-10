from __future__ import absolute_import

import logging
import os

from django.utils import six, importlib
from mongoengine.connection import connect
from six import string_types
try:
    import urlparse
except:
    from urllib import parse as urlparse


__settings = None


def is_dataframe(obj):
    try:
        import pandas as pd
        return isinstance(obj, pd.DataFrame)
    except:
        return False


def is_series(obj):
    try:
        import pandas as pd
        return isinstance(obj, pd.Series) and not isinstance(obj, pd.DataFrame)
    except:
        return False


def is_estimator(obj):
    try:
        from sklearn.base import BaseEstimator
        from sklearn.pipeline import Pipeline
        return isinstance(obj, (BaseEstimator, Pipeline))
    except:
        False


def is_ndarray(obj):
    try:
        import numpy as np
        return isinstance(obj, np.ndarray)
    except:
        False


def is_spark_mllib(obj):
    """
    # unlike scikit learn obj is not the actual model, but a specification of
    # the model for the spark server to create. so obj is the name of the
    # python class, e.g. obj=pyspark.mllib.clustering.KMeans
    """
    if isinstance(obj, string_types):
        return 'pyspark.mllib' in obj
    return False


def settings():
    """ wrapper to get omega settings from either django or omegamldefaults """
    import omegaml.defaults as omdefaults
    global __settings
    if __settings is not None:
        return __settings
    try:
        # see if we're running as a django app
        # DEBUG will probably always be as a djangon setting configuraiton
        from django.conf import settings as djsettings  # @UnresolvedImport
        defaults = djsettings
        # this is to test if django was initialized. if not revert
        # to using omdefaults
        try:
            getattr(defaults, 'SECRET_KEY')
        except:
            from warnings import warn
            warn("Using omegaml.defaults because Django was not initialized."
                 "Try importing omegaml within a method instead of at the "
                 "module level")
            raise
    except Exception as e:
        defaults = omdefaults
    else:
        # get default omega settings into django settings if not set
        # there already
        import omegaml.defaults as omdefaults
        for k in dir(omdefaults):
            if not hasattr(defaults, k):
                setattr(defaults, k, getattr(omdefaults, k))
    __settings = defaults
    return __settings


def override_settings(**kwargs):
    """ test support """
    cfgvars = settings()
    for k, v in six.iteritems(kwargs):
        setattr(cfgvars, k, v)
    # -- OMEGA_CELERY_CONFIG updates
    celery_config = getattr(cfgvars, 'OMEGA_CELERY_CONFIG', {})
    for k in [k for k in kwargs.keys() if k.startswith('OMEGA_CELERY')]:
        celery_k = k.replace('OMEGA_', '')
        celery_config[celery_k] = kwargs[k]
    setattr(cfgvars, 'OMEGA_CELERY_CONFIG', celery_config)


def delete_database():
    """ test support """
    host = settings().OMEGA_MONGO_URL
    parsed_url = urlparse.urlparse(host)
    database_name = parsed_url.path[1:]
    client = connect(database_name, host=parsed_url.netloc)
    client.drop_database(database_name)


def make_tuple(arg):
    if not isinstance(arg, (list, tuple)):
        arg = (arg,)
    return tuple(arg)


def make_list(arg):
    if not isinstance(arg, (list)):
        arg = list(arg)
    return arg


def flatten_columns(col, sep='_'):
    # source http://stackoverflow.com/a/29437514
    if not type(col) is tuple:
        return col
    else:
        new_col = ''
        for leveli, level in enumerate(col):
            if not level == '':
                if not leveli == 0:
                    new_col += sep
                new_col += level
        return new_col


def load_class(requested_class):
    """
    Check if requested_class is a string, if so attempt to load
    class from module, otherwise return requested_class as is
    """
    if isinstance(requested_class, six.string_types):
        module_name, class_name = requested_class.rsplit(".", 1)
        try:
            m = importlib.import_module(module_name)
            return getattr(m, class_name)
        except:
            logging.debug(
                'could not load module %s for class %s' % (
                    module_name, class_name))
            raise
    return requested_class


def get_rdd_from_df(df):
    """
    takes a pandas df and returns a spark RDD
    """
    from pyspark import SparkContext, SQLContext
    from pyspark.mllib.linalg import Vectors
    sc = SparkContext.getOrCreate()
    from warnings import warn
    warn(
        "get_rdd_from_df creates a spark context, it is recommended"
        " that you use SparkContext.getOrCreate() to prevent multiple context"
        " creation")
    sqlContext = SQLContext(sc)
    spark_df = sqlContext.createDataFrame(df)
    rdd = spark_df.rdd.map(lambda data: Vectors.dense(
        [float(x) for x in data]))
    return rdd


def get_labeledpoints(Xname, Yname):
    """
    returns a labeledpoint RDD from the datasets provided
    """
    import omegaml as om
    from pyspark.mllib.regression import LabeledPoint
    # import from datastore
    X = om.datasets.get(Xname)
    Y = om.datasets.get(Yname)
    result = Y.join(X)
    # create labeled point
    rdd = get_rdd_from_df(result)
    labeled_point = rdd.map(lambda x: LabeledPoint(float(x[0]), x[1:]))
    return labeled_point


def get_labeled_points_from_rdd(rdd):
    """
    returns a labeledpoint from the RDD provided
    """
    from pyspark.mllib.regression import LabeledPoint
    return rdd.map(lambda x: LabeledPoint(float(x[0]), x[1:]))


def unravel_index(df):
    """ 
    convert index columns into dataframe columns

    index columns are stored in the dataframe, named '_idx#<n>_<name>'
    where n is the sequence and name is the nth index name.

    Use restore_index_columns_order to get back the original index columns
    in sequence.

    :param df: the dataframe
    :return: the unravelled dataframe, meta
    """
    # remember original names
    idx_meta = {
        'names': df.index.names,
    }
    # convert index names so we can restore them later
    store_idxnames = ['_idx#{}_{}'.format(i, name or i)
                      for i, name in enumerate(idx_meta['names'])]
    df.index.names = store_idxnames
    unravelled = df.reset_index(), idx_meta
    # restore index names on original dataframe
    df.index.names = idx_meta['names']
    return unravelled


def restore_index_columns_order(columns):
    """
    from an iterable of column names get the index columns in sequence order

    index columns are named '_idx#<n>_<name>' where n is the sequence
    of the original index column and name is the name
    """
    def get_index_order(col):
        if '_idx#' in col:
            n = col.split('_')[1].split('#')[1]
        else:
            n = 0
        return n
    index_cols = (col for col in columns if col and col.startswith('_idx'))
    index_cols = sorted(index_cols, key=get_index_order)
    return index_cols


def restore_index(df, idx_meta):
    """
    restore index proper

    :parm
    """
    # -- get index columns
    index_cols = restore_index_columns_order(df.columns)
    # -- set index columns
    result = df.set_index(index_cols) if index_cols else df
    if index_cols:
        result.index.names = idx_meta.get('names', [None] * len(index_cols))
    return result


def jsonescape(s):
    return str(s).replace('.', '_')


def grouper(n, iterable):
    # https://stackoverflow.com/a/8998040
    import itertools
    it = iter(iterable)
    while True:
        chunk_it = itertools.islice(it, n)
        try:
            first_el = next(chunk_it)
        except StopIteration:
            return
        yield itertools.chain((first_el,), chunk_it)


def cursor_to_dataframe(cursor, chunk_size=10000):
    # a faster and less memory hungry variant of DataFrame.from_records
    # works by building a set of smaller dataframes to reduce memory
    # consumption. Note chunks are of size max. chunk_size.
    import pandas as pd
    frames = []
    count = cursor.count()
    if count > 0:
        chunk_size = max(chunk_size, int(count * .1))
        for chunk in grouper(chunk_size, cursor):
            frames.append(pd.DataFrame.from_records(chunk))
        if frames:
            df = pd.concat(frames)
        else:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()
    return df


def reshaped(data):
    """
    check if data is 1d and if so reshape to a column vector
    """
    import pandas as pd
    import numpy as np
    if isinstance(data, (pd.Series, pd.DataFrame)):
        if len(data.shape) == 1:
            data = data.values.reshape(-1, 1)
    elif isinstance(data, np.ndarray):
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)
    elif isinstance(data, list):
        data = np.array(data)
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)
    return data
