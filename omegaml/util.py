from __future__ import absolute_import

import pathlib

from pathlib import Path

from copy import deepcopy
from importlib import import_module

import json
import logging
import os
import sys
import tempfile
import uuid
import warnings
from base64 import b64encode
from bson import UuidRepresentation
from datetime import datetime
from shutil import rmtree

try:
    import urlparse
except:
    from urllib import parse as urlparse

logger = logging.getLogger(__name__)

import pandas as pd

try:
    from pandas import json_normalize
except Exception as e:
    # support pandas < 1.0
    try:
        from pandas.io.json import json_normalize
    except:
        raise e
json_normalize = json_normalize

# reset global settings
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
    if isinstance(obj, str):
        return 'pyspark.mllib' in obj
    return False


def settings(reload=False):
    """ wrapper to get omega settings from either django or omegaml.defaults

    This is a settings (defaults) loader. It returns a cached DefaultsContext
    that is initialised from omegaml.defaults. When running in Django, the
    Django settings will be used to override omegaml.defaults values.

    Usage:
        # on first call, intialise a DefaultsContext
        # on subsequent calls, return this DefaultsContext as is
        defaults = settings()

        # reload DefaultsContext from environment
        defaults = settings(reload=True)

        Note reload=True is 2.5x slower than reload=False. You should only
        reload=True if you need to ensure a fresh environment is loaded, e.g.
        when switching users in the same python process.

        %timeit settings()
        490 ns ± 13.1 ns per loop (mean ± std. dev. of 7 runs, 1000000 loops each)

        %timeit settings(reload=True)
        1.31 ms ± 10.7 µs per loop (mean ± std. dev. of 7 runs, 1000 loops each)

    Caution:
        If your code uses DefaultsContext based on user configuration you MUST
        ensure to call settings(reload=True) before switching the configuration.
        Not doing so risks leaking information from the old user configuration
        to the new.
    """
    from omegaml import _base_config as omdefaults
    global __settings
    if not reload and __settings is not None:
        return __settings
    try:
        # see if we're running as a django app
        from django.contrib.auth.models import User
        from django.conf import settings as djsettings  # @UnresolvedImport
        try:
            getattr(djsettings, 'SECRET_KEY')
        except Exception as e:
            from warnings import warn
            warn("Using omegaml.defaults because Django was not initialized."
                 "Try importing omegaml within a method instead of at the "
                 "module level")
            raise
        else:
            defaults = djsettings
    except Exception as e:
        # django failed to initialize, use omega defaults
        defaults = omdefaults
    else:
        # get default omega settings into django settings if not set there
        from omegaml import _base_config as omdefaults
        for k in dir(omdefaults):
            if k.isupper() and not hasattr(defaults, k):
                setattr(defaults, k, getattr(omdefaults, k))
    __settings = DefaultsContext(defaults)
    omdefaults.load_config_file(vars=__settings)
    omdefaults.update_from_env(vars=__settings)
    omdefaults.load_framework_support(vars=__settings)
    omdefaults.load_user_extensions(vars=__settings)
    return __settings


def override_settings(**kwargs):
    """ test support """
    cfgvars = settings()
    for k, v in kwargs.items():
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
    if isinstance(requested_class, str):
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
    # treat particular index types
    if isinstance(df.index, pd.DatetimeIndex):
        if getattr(df.index, 'freq') is not None:
            idx_meta['freq'] = getattr(df.index.freq, 'name', None)
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

    index_cols = (col for col in columns if isinstance(col, str) and col.startswith('_idx'))
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
    if isinstance(result.index, pd.DatetimeIndex):
        # restore datetime frequency, if possible
        if 'freq' in idx_meta:
            try:
                freq = idx_meta.get('freq')
                freq = freq or pd.infer_freq(result.index)
                result = result.asfreq(freq)
            except:
                pass
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
    if hasattr(cursor, 'count_documents'):
        count = cursor.count_documents()
        chunk_size = max(chunk_size, int(count * .1))
    else:
        # CommandCursors don't have .count_documents, go as long as we can
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


def ensure_index(coll, idx_specs, replace=False, **kwargs):
    """
    ensure a pymongo index specification exists on a given collection

    Checks if the index exists in regards to the fields in the specification.
    Only checks for field names, not sort order.

    Args:
        coll (pymongo.Collection): mongodb collection
        idx_specs (dict): specs as field => sort order

    Returns:
        None
    """
    from omegaml.store.queryops import ensure_index_limit

    idx_keys = list(dict(dict(v)['key']).keys() for v in coll.list_indexes())
    index_exists = any(all(k in keys for k in dict(idx_specs).keys()) for keys in idx_keys)
    idx_specs_SON = list(dict(idx_specs).items())
    # finally create or replace index
    created = False
    should_drop = index_exists and replace
    should_create = not index_exists
    if should_drop or should_create:
        idx_specs, idx_kwargs = ensure_index_limit(idx_specs_SON, **kwargs)
    if should_drop:
        coll.drop_index(idx_specs, **idx_kwargs)
        should_create = True
    if should_create:
        coll.create_index(idx_specs, **idx_kwargs)
        created = True
    return created


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
    tzinfo_pattern = re.compile(r'datetime64\[ns, (.*)\]')
    for col, dtype in dtypes.items():
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
    """
    A pickable pymongo.Collection

    This enables clean transmission of Collection instances to other processes, e.g.
    for multiprocessing tasks. It works by pickling the collection's connection data
    and restoring the database connection on unpickling.

    Usage:
        from multiprocessing import Pool

        def process(job):
            data, coll = job
            coll.insert_one(data)

        coll = PickableCollection(coll)
        p = Pool()
        p.map(process, zip(range(1000), repeat(coll))
    """

    def __init__(self, collection):
        super(PickableCollection, self).__setattr__('collection', collection)
        self._pkl_cloned = False

    def __getattr__(self, k):
        return getattr(self.collection, k)

    def __setattr__(self, k, v):
        return setattr(self.collection, k, v)

    def __getitem__(self, k):
        return self.collection[k]

    def __setitem__(self, k, v):
        self.collection[k] = v

    def __getstate__(self):
        client = self.database.client
        host, port = list(client.nodes)[0]
        # options contains ssl settings
        options = self.database.client._MongoClient__options._options
        # extract credentials in pickable format
        if hasattr(self.database.client, '_MongoClient__all_credentials'):
            # pymongo < 4.1
            all_creds = self.database.client._MongoClient__all_credentials
            # -- if authSource was used for connection, credentials are in 'admin'
            # -- otherwise credentials are keyed by username
            cred_key = 'admin' if 'admin' in all_creds else options['username']
            creds = all_creds[cred_key]
        else:
            # pymongo >= 4.1
            creds = self.database.client.options.pool_options._credentials
        creds_state = dict(creds._asdict())
        creds_state.pop('cache')
        creds_state['source'] = str(creds.source)
        # https://github.com/mongodb/mongo-python-driver/blob/087950d869096cf44a797f6c402985a73ffec16e/pymongo/common.py#L161
        UUID_REPS = {
            UuidRepresentation.STANDARD: 'standard',
            UuidRepresentation.PYTHON_LEGACY: 'pythonLegacy',
        }
        options['uuidRepresentation'] = UUID_REPS.get(options.get('uuidRepresentation'), 'standard')
        return {
            'name': self.name,
            'database': self.database.name,
            'host': host,
            'port': port,
            'credentials': creds_state,
            'options': options,
        }

    def __setstate__(self, state):
        from omegaml.mongoshim import MongoClient
        url = 'mongodb://{username}:{password}@{host}:{port}/{database}'.format(**state, **state['credentials'])
        # ClientOptions calls it serverselectiontimeoutms, but stores seconds
        # MongoClient however, on recreating in unpickling, requires milliseconds
        # https://pymongo.readthedocs.io/en/stable/api/pymongo/mongo_client.html?highlight=serverSelectionTimeoutMS#pymongo.mongo_client.MongoClient
        # https://github.com/mongodb/mongo-python-driver/blob/7a539f227a9524b27ef469826ef9ee5bd4533773/pymongo/common.py
        # https://github.com/mongodb/mongo-python-driver/blob/master/pymongo/client_options.py#L157
        options = state['options']
        options['serverSelectionTimeoutMS'] = options.pop('serverselectiontimeoutms', 30) * 1000
        client = MongoClient(url, authSource=state['credentials']['source'], **options)
        db = client.get_database()
        collection = db[state['name']]
        super(PickableCollection, self).__setattr__('collection', collection)
        self._pkl_cloned = True

    def __repr__(self):
        return 'PickableCollection({})'.format(repr(self.collection))


def extend_instance(obj, cls, *args, conditional=None, **kwargs):
    """Apply mixins to a class instance after creation"""
    # source https://stackoverflow.com/a/31075641
    from omegaml import load_class
    cls = load_class(cls)
    base_mro = obj.__class__.mro()
    should_apply = True if not callable(conditional) else conditional(cls, obj)
    if should_apply and cls not in base_mro:
        base_cls = obj.__class__
        base_cls_name = base_mro[-2].__name__
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
    """
    om.defaults as set for a particular Omega() instance

    Usage:
        defaults = DefaultsContext(source)

        # attribute access
        defaults.SOME_VARIABLE
        defaults['SOME_VARIABLE']
        defaults.get('SOME_VARIABLE', default=None)

        were source is a module or a settings object (any object with
        any number of .UPPERCASE_VARIABLE attributes). Source will be
        deep-copied to ensure DefaultsContext cannot be changed by external
        references.
    """

    def __init__(self, source):
        for k in dir(source):
            if k.isupper():
                value = getattr(source, k)
                setattr(self, k, deepcopy(value))

    def keys(self):
        return [v for v in dir(self) if v.isupper()]

    def __iter__(self):
        for k in dir(self):
            if k.startswith('OMEGA') and k.isupper():
                yield k

    def __getitem__(self, k):
        if k in dir(self):
            return getattr(self, k)
        raise KeyError(k)

    def __setitem__(self, k, v):
        setattr(self, k, v)

    def __delitem__(self, k):
        delattr(self, k)

    def get(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            return default

    def __repr__(self):
        d = {k: self[k] for k in self.keys()}
        return 'DefaultsContext({})'.format(repr(d))


def ensure_json_serializable(v):
    import numpy as np
    import pandas as pd
    if isinstance(v, np.ndarray):
        return v.flatten().tolist()
    if isinstance(v, pd.Series):
        return ensure_json_serializable(v.to_dict())
    elif isinstance(v, range):
        v = list(v)
    elif isinstance(v, dict):
        vv = {
            k: ensure_json_serializable(v)
            for k, v in v.items()
        }
        v = vv
    return v


def mkdirs(path):
    """ safe os.makedirs for python 2 & 3
    """
    if not os.path.exists(path):
        os.makedirs(path)


def base_loader(_base_config):
    # load base classes
    # -- this does not instantiate, only setup env
    # -- om.setup() does actual loading
    _omega = None

    def load_customized():
        mod = import_module(os.environ.get('OMEGA_CUSTOM_LOADER', ''))
        _omega = mod.omega
        _base_config_client = mod.defaults
        _base_config.update_from_obj(_base_config_client, attrs=_base_config)
        return _omega, 'custom'

    def load_commercial():
        from omegaee import omega as _omega
        from omegaee import eedefaults as _base_config_ee
        _base_config.update_from_obj(_base_config_ee, attrs=_base_config)
        return _omega, 'commercial'

    def load_base():
        from omegaml import omega as _omega
        return _omega, 'base configuration'

    loaders = load_customized, load_commercial, load_base
    for loader in loaders:
        try:
            logger.debug(f'attempting to load omegaml from {loader}')
            _omega, source = loader()
        except Exception as e:
            logger.debug(f'failed to load omegaml from {loader}, {e}')
        else:
            logger.debug(f'succeeded to load omegaml from {loader}')
            logger.info(f'loaded omegaml from {source}')
            break

    settings(reload=True)
    return _omega


from io import StringIO

from contextlib import contextmanager
import re


def markup(file_or_str, parsers=None, direct=True, on_error='warn', default=None, msg='could not read {}',
           **kwargs):
    """
    a safe markup file reader, accepts json and yaml, returns a dict or a default
    Usage:
        file_or_str = filename|file-like|markup-str
        # try, return None if not readable, will issue a warning in the log
        data = markup(file_or_str)
        # try, return some other default, will issue a warning in the log
        data = markup(file_or_str, default={})
        # try and fail
        data = markup(file_or_str, on_error='fail')
    Args:
        file_or_str (None, str, file-like): any file-like, can be
           any object that the parsers accept
        parsers (list): the list of parsers, defaults to json.load, yaml.safe_load,
           json.loads
        direct (bool): if True returns the result, else returns markup (self). then use
           .read() to actually read the contents
        on_error (str): 'fail' raises a ValueError in case of error, 'warn' outputs a warning to the log,
           and returns the default, 'silent' returns the default. Defaults to warn
        default (obj): return the obj if the input is None or in case of on_error=warn or silent
        **kwargs (dict): any kwargs passed on to read(), any entry that matches a parser
            function's module name will be passed on to the parser
    Returns:
        data parsed or default
        markups.exceptions contains list of exceptions raised, if any
    """
    # source: https://gist.github.com/miraculixx/900a28a94c375b7259b1f711b93417d3
    import json
    import yaml
    import logging
    import pathlib

    parsers = parsers or (json.load, yaml.safe_load, json.loads)
    pathlike = lambda s: pathlib.Path(s).exists()

    @contextmanager
    def fopen(filein, *args, **kwargs):
        # https://stackoverflow.com/a/55032634/890242
        if isinstance(filein, str) and pathlike(filein):  # filename
            with open(filein, *args, **kwargs) as f:
                yield f
        elif isinstance(filein, str):  # some other string, make a file-like
            yield StringIO(filein)
        elif hasattr(filein, 'read'):
            # file-like object
            yield filein

    throw = lambda ex: (_ for _ in ()).throw(ex)
    exceptions = []

    def read(**kwargs):
        if file_or_str is None:
            return default
        for fn in parsers:
            try:
                with fopen(file_or_str) as fin:
                    if hasattr(fin, 'seek'):
                        fin.seek(0)
                    data = fn(fin, **kwargs.get(fn.__module__, {}))
            except Exception as e:
                exceptions.append(e)
            else:
                return data
        # nothing worked so far
        actions = {
            'fail': lambda: throw(ValueError("Reading {} caused exceptions {}".format(file_or_str, exceptions))),
            'warn': lambda: logging.warning(msg.format(file_or_str)) or default,
            'silent': lambda: default,
        }
        return actions[on_error]()

    markup.read = read
    markup.exceptions = exceptions
    return markup.read(**kwargs) if direct else markup


def raises(fn, wanted_ex):
    try:
        fn()
    except Exception as e:
        assert isinstance(e, wanted_ex), "expected {}, raised {} instead".format(wanted_ex, e)
    else:
        raise ValueError("did not raise {}".format(wanted_ex))
    return True


def dict_merge(destination, source, delete_on='__delete__', subset=None):
    """
    Merge two dictionaries, including sub dicts

    Args:
        destination (dict): the dictionary to merge into
        source (dict): the dictionary to merge from
        delete_on (obj): for each entry in source, its value is
            compared to match delete_on, if it does the key will
            be deleted in the destination dict. Defaults to '__delete__'
        subset (callable): optional, only merge item
            if subset(key, value) is True

    See Also:
        https://stackoverflow.com/a/20666342/890242
    """
    dict_merge.DELETE = delete_on
    for key, value in source.items():
        if callable(subset) and not subset(key, value):
            continue
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            dict_merge(node, value, delete_on=delete_on)
        else:
            if value == dict_merge.DELETE and key in destination:
                del destination[key]
            else:
                destination[key] = value
    return destination


def ensure_base_collection(collection):
    """ get base from pymongo.Collection subclass instance """
    from pymongo.collection import Collection
    is_real_collection = isinstance(collection, Collection)
    while not is_real_collection:
        collection = collection.collection
        is_real_collection = isinstance(collection, Collection)
    return collection


def reorder(df, specs):
    """ build reordered column selector given specs

    Takes a dataframe and returns a column selector accordingly.
    This is convenient to reorder a large number of
    """
    selector = []
    for c in specs.split(','):
        if c == '*':
            selector.extend(sorted(set(df.columns) - set(selector)))
        else:
            if c in selector:
                selector.remove(c)
            selector.append(c)
    return selector


def migrate_unhashed_datasets(store):
    """ Migrate the names of previously unhashed datasets (collections)

    Args:
        store: the OmegaStore instance, e.g. om.datasets

    Returns:
        list of migrated dataset tuples(name, unhashed_collection_name,
        hashed_collection_name)
    """
    assert store.defaults.OMEGA_STORE_HASHEDNAMES, "OMEGA_STORE_HASEHDNAMES must be set to True for this to work"
    migrated = []
    for dsmeta in store.list(hidden=True, raw=True):
        dsname = dsmeta.name
        ext = dsname.split('.')[-1]
        hashed_name = store.object_store_key(dsname, ext)
        if dsmeta.collection is not None:
            unhashed_coll_name = dsmeta.collection
            unhashed_coll = store.mongodb[unhashed_coll_name]
            # get the new collection name, rename
            unhashed_coll.rename(hashed_name)
            # remember new name
            dsmeta.collection = hashed_name
            dsmeta.save()
            migrated.append((dsname, unhashed_coll_name, hashed_name))
    return migrated


class MongoEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types

    adopted from https://stackoverflow.com/a/49677241/890242
                 https://stackoverflow.com/a/11875813/890242
    """

    def default(self, obj):
        import numpy as np

        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient='records')
        elif isinstance(obj, pd.Series):
            return obj.tolist()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, pd.Timedelta):
            return obj.value()
        elif isinstance(obj, bytes):
            return b64encode(obj).decode('utf8')
        elif isinstance(obj, range):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


json_dumps_np = lambda *args, cls=None, **kwargs: json.dumps(*args, **kwargs, cls=cls or MongoEncoder)
mongo_compatible = lambda *args: json.loads(json_dumps_np(*args))


def tryOr(fn, else_fn):
    # try fn(), if exception call else_fn() if callable, return its value otherwise
    try:
        return fn()
    except:
        return else_fn() if callable(else_fn) else else_fn


# https://stackoverflow.com/a/58466875/890242
_raise = lambda ex: (_ for _ in ()).throw(ex)


class IterableJsonDump(list):
    """ dump iterable of json data """

    # adapted from https://stackoverflow.com/a/45143995/890242
    def __init__(self, generator, transform=None):
        self.generator = generator
        self._len = 1
        self._transform = transform or (lambda o: o)

    def __iter__(self):
        self._len = 0
        for item in self.generator:
            yield self._transform(item)
            self._len += 1

    def __len__(self):
        return self._len

    @classmethod
    def dump(cls, iterlike, fout, transform=None, **kwargs):
        gen = IterableJsonDump(iterlike, transform=transform)
        for chunk in json.JSONEncoder(**kwargs).iterencode(gen):
            fout.write(chunk)

    @classmethod
    def dumps(cls, iterlike, **kwargs):
        buffer = StringIO()
        cls.dump(iterlike, buffer, **kwargs)
        return buffer.getvalue()


isTrue = lambda v: v if isinstance(v, bool) else (v.lower() in ['yes', 'y', 't', 'true', '1'])


class SystemPosixPath(type(Path()), Path):
    """ a pathlib.Path shim that renders with Posix path.sep on all systems

    Usage:
        path = SystemPosixPath('./foo/bar')
        => will give a WindowsPath | PosixPath
        => str(path) => will always be './foo/bar')

    Rationale:
        pathlib.Path('./foo/bar') will render as '\\foo\bar' on Windows
        while pathlib.PosixPath cannot be imported in Windows
    """

    def __str__(self):
        # on windows, return a posix path
        # on posix systems, this is a noop
        path = super().__str__()
        return path if os.name != 'nt' else path.replace('\\', '/')


class ProcessLocal(dict):
    def __init__(self, *args, **kwargs):
        self._pid = os.getpid()
        super().__init__(*args, **kwargs)

    def _check_pid(self):
        if self._pid != os.getpid():
            self.clear()
            self._pid = os.getpid()

    def __getitem__(self, k):
        self._check_pid()
        return super().__getitem__(k)

    def keys(self):
        self._check_pid()
        return super().keys()

    def __contains__(self, item):
        self._check_pid()
        return super().__contains__(item)


class KeepMissing(dict):
    # a missing '{key}' is replaced by '{key}'
    # in order to avoid raising KeyError
    # see str.format_map
    def __missing__(self, key):
        return '{' + key + '}'

