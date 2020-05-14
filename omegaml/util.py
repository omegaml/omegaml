from __future__ import absolute_import

import warnings
from importlib import import_module

import logging
import os
import re
import six
import sys
import tempfile
import uuid
from shutil import rmtree
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


def settings(reload=False):
    """ wrapper to get omega settings from either django or omegamldefaults """
    from omegaml import _base_config as omdefaults
    global __settings
    if not reload and __settings is not None:
        return __settings
    try:
        # see if we're running as a django app
        from django.utils import six
        from django.utils.functional import empty
        from django.conf import settings as djsettings  # @UnresolvedImport
        defaults = djsettings
        # this is to test if django was initialized. if not revert
        # to using omdefaults
        try:
            if defaults._wrapped is empty:
                # django is not initialized, use omega defaults
                raise ValueError()
            getattr(defaults, 'SECRET_KEY')
        except Exception as e:
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
        from omegaml import _base_config as omdefaults
        for k in dir(omdefaults):
            if k.isupper() and not hasattr(defaults, k):
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
    from omegaml.mongoshim import MongoClient

    mongo_url = settings().OMEGA_MONGO_URL
    parsed_url = urlparse.urlparse(mongo_url)
    database_name = parsed_url.path[1:]
    # authenticate via admin db
    # see https://stackoverflow.com/a/20554285
    c = MongoClient(mongo_url, authSource='admin')
    c.drop_database(database_name)


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


CLASS_CACHE = {}


def load_class(requested_class):
    """
    Check if requested_class is a string, if so attempt to load
    class from module, otherwise return requested_class as is
    """
    import importlib
    if isinstance(requested_class, six.string_types):
        if requested_class in CLASS_CACHE:
            return CLASS_CACHE.get(requested_class)
        module_name, class_name = requested_class.rsplit(".", 1)
        try:
            m = importlib.import_module(module_name)
            cls = getattr(m, class_name)
            CLASS_CACHE[requested_class] = cls
            return cls
        except Exception as e:
            logging.debug(
                'could not load module %s for class %s due to %s. sys.path=%s' % (
                    module_name, class_name, str(e), str(sys.path)))
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


def unravel_index(df, row_count=0):
    """
    convert index columns into dataframe columns

    index columns are stored in the dataframe, named '_idx#<n>_<name>'
    where n is the sequence and name is the nth index name.

    Use restore_index_columns_order to get back the original index columns
    in sequence.

    :param df: the dataframe
    :param row_count: the row_count base, ensures subsequent stores
      get differnt row ids
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
    unravelled_df, idx_meta = df.reset_index(), idx_meta
    # store row ids
    unravelled_df['_om#rowid'] = unravelled_df.index.values + row_count
    # restore index names on original dataframe
    df.index.names = idx_meta['names']
    return unravelled_df, idx_meta


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

    index_cols = (col for col in columns if isinstance(col, six.string_types) and col.startswith('_idx'))
    index_cols = sorted(index_cols, key=get_index_order)
    return index_cols


def restore_index(df, idx_meta, rowid_sort=True):
    """
    restore index proper

    :param df: the dataframe
    :param idx_meta: index metadata
    :param rowid_sort: whether to sort by row id. defaults to True
           If your query is already sorted in some specific way,
           specify False to keep the sort order.
    """
    # -- establish row order proper
    if rowid_sort and '_om#rowid' in df:
        df.sort_values('_om#rowid', inplace=True)
        del df['_om#rowid']
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


def cursor_to_dataframe(cursor, chunk_size=10000, parser=None):
    # a faster and less memory hungry variant of DataFrame.from_records
    # works by building a set of smaller dataframes to reduce memory
    # consumption. Note chunks are of size max. chunk_size.
    import pandas as pd
    frames = []
    if hasattr(cursor, 'count'):
        count = cursor.count()
        chunk_size = max(chunk_size, int(count * .1))
    else:
        # CommandCursors don't have .count, go as long as we can
        count = None
    if count is None or count > 0:
        for chunk in grouper(chunk_size, cursor):
            df = pd.DataFrame.from_records(chunk) if not parser else parser(r for r in chunk)
            frames.append(df)
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
        else:
            if len(data.shape) == 2 and data.shape[1] == 1:
                data = data.values.reshape(-1, 1)
    elif isinstance(data, np.ndarray):
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)
    elif isinstance(data, list):
        data = np.array(data)
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)
    return data


def gsreshaped(data):
    """
    gridsearch reshape values according to GridSearchCV.fit

    see https://stackoverflow.com/a/49241326
    """
    import pandas as pd
    import numpy as np
    if isinstance(data, (pd.Series, pd.DataFrame)):
        if len(data.shape) == 2 and data.shape[1] == 1:
            data = data.values.reshape(-1)
    elif isinstance(data, np.ndarray):
        if len(data.shape) == 2 and data.shape[1] == 1:
            data = data.reshape(-1)
    return data


def convert_dtypes(df, dtypes):
    """
    get back original dtypes

    :param df: the dataframe to apply conversion to
    :param dtypes: the dict mapping column to dtype (use kind_meta['dtypes'])
    """
    # tz pattern used in convert_dtypes
    tzinfo_pattern = re.compile('datetime64\[ns, (.*)\]')
    for col, dtype in six.iteritems(dtypes):
        if dtype.startswith('datetime'):
            if not hasattr(df, 'dtypes'):
                continue
            try:
                match = tzinfo_pattern.match(dtype)
                if match:
                    tzname = match.groups()[0]
                    df[col] = df[col].dt.tz_localize('UTC').dt.tz_convert(tzname)
            except:
                # TODO ignore errors, issue warning
                pass

    return df


class PickableCollection(object):
    def __init__(self, collection):
        super(PickableCollection, self).__setattr__('collection', collection)

    def __getattr__(self, k):
        return getattr(self.collection, k)

    def __setattr__(self, k, v):
        return setattr(self.collection, k, v)

    def __getitem__(self, k):
        return self.collection[k]

    def __setitem__(self, k, v):
        self.collection[k] = v

    def __getstate__(self):
        client = self.collection._Collection__database._Database__client
        host, port = list(client.nodes)[0]
        return {
            'name': self.name,
            'database': self.database.name,
            'host': host,
            'port': port,
            'credentials': self.database.client._MongoClient__all_credentials[self.database.name],
        }

    def __setstate__(self, state):
        from omegaml.mongoshim import MongoClient
        url = 'mongodb://{credentials.username}:{credentials.password}@{host}:{port}/{database}'.format(**state)
        client = MongoClient(url, authSource=state['credentials'].source)
        db = client.get_database()
        collection = db[state['name']]
        super(PickableCollection, self).__setattr__('collection', collection)

    def __repr__(self):
        return 'PickableCollection({})'.format(repr(self.collection))


def extend_instance(obj, cls, *args, **kwargs):
    """Apply mixins to a class instance after creation"""
    # source https://stackoverflow.com/a/31075641
    from omegaml import load_class
    cls = load_class(cls)
    if cls not in obj.__class__.mro():
        base_cls = obj.__class__
        base_cls_name = 'Extended{}'.format(obj.__class__.__name__.split('.')[0])
        obj.__class__ = type(base_cls_name, (cls, base_cls), {})
    if hasattr(obj, '_init_mixin'):
        obj._init_mixin(*args, **kwargs)


def temp_filename(dir=None, ext='tmp'):
    """ generate a temporary file name """
    dir = dir or tempfile.mkdtemp()
    return os.path.join(dir, uuid.uuid4().hex + f'.{ext}')


def remove_temp_filename(fn, dir=True):
    dirname = os.path.dirname(fn)
    os.remove(fn)
    if dir:
        if dirname.startswith('/tmp/') and len(dirname.split('/')) > 1:
            rmtree(dirname)
        else:
            warnings.warn('will not remove directory {} as it is outside of /tmp'.format(fn))


def ensure_python_array(arr, dtype):
    import numpy as np
    return np.array(arr).astype(dtype)


def dict_update_if(condition, dict, other):
    try:
        condition()
    except:
        pass
    else:
        dict.update(other)


def module_available(modname):
    try:
        import_module(modname)
    except:
        return False
    return True


def tensorflow_available():
    return module_available('tensorflow')


def keras_available():
    return module_available('keras')


def calltrace(obj):
    """
    trace calls on an object

    Usage:
        .. code ::

            def __init__(self, *args, **kwargs):
                calltrace(self)

        This will print the method arguments and return values
        for every call. Exceptions will be caught and printed,
        then re-raised. Magic methods are not traced.

    Args:
        obj: the object to trace
    """

    def tracefn(el):
        def methodcall(*args, **kwargs):
            print("calling", el, args, kwargs)
            try:
                result = el(*args, **kwargs)
            except (BaseException, Exception) as e:
                print("=> ", str(e))
                raise
            except:
                print("=> unknown exception")
                raise
            else:
                print("=> ", result)
            return result

        return methodcall

    for item in dir(obj):
        if item.startswith('__'):
            continue
        el = getattr(obj, item)
        if type(el).__name__ == 'method':
            setattr(obj, item, tracefn(el))
    return obj


class DefaultsContext(object):
    def __init__(self, source):
        for k in dir(source):
            if k.isupper():
                setattr(self, k, getattr(source, k))

    def __iter__(self):
        for k in dir(self):
            if k.startswith('OMEGA') and k.isupper():
                yield k, getattr(self, k)

    def __repr__(self):
        return '{}'.format(dict(self))


def ensure_json_serializable(v):
    import numpy as np
    import pandas as  pd
    if isinstance(v, np.ndarray):
        return v.flatten().tolist()
    if isinstance(v, pd.Series):
        return ensure_json_serializable(v.to_dict())
    elif isinstance(v, dict):
        vv = {
            k: ensure_json_serializable(v)
            for k, v in six.iteritems(v)
        }
        return vv
    return v


def mkdirs(path):
    """ safe os.makedirs for python 2 & 3
    """
    if not os.path.exists(path):
        os.makedirs(path)
