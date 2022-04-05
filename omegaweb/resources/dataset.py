"""
REST API to datasets
"""


from mongoengine.errors import DoesNotExist
from six import iteritems
from tastypie.authentication import ApiKeyAuthentication
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.fields import CharField, DictField
from tastypie.http import HttpNotFound
from tastypie.resources import Resource

import numpy as np
from omegaweb.resources.omegamixin import OmegaResourceMixin
from omegaweb.resources.util import isTrue
import pandas as pd
from six.moves import builtins
from six.moves import urllib

from .util import BundleObj


class DatasetResource(OmegaResourceMixin, Resource):

    """
    DatasetResource implements the REST api to omegaml.datasets
    """
    data = DictField('data',
                     help_text=('the data as a dictionary. see the Pandas '
                                'DataFrame.to_dict() for details'))
    """ the dataset's content as a dictionary (required)
    
    Depending on the :code:`orient` field the data dictionary will have a 
    different layout.
    
    * :code:`orient='dict'`: column => { row-id: value, ... }
    * :code:`orient='records'`: rows => [ { column: value }, ...]
    """
    index = DictField('index', blank=True, null=True,
                      help_text=('the index type and values. A dictionary '
                                 'of { type => str, values => list }'))
    """ the index type and values
    
    a dictionary of form { type: index-type, values: list }
    """
    dtypes = DictField('dtypes', blank=True, null=True,
                       help_text=('the data types of each column. A '
                                  'dictionary of { column => type }'))
    """ the data types of each column (optional)
    
    Use this to convert the value in :code:`data` to the corresponding 
    type on the client platform. Note that in some instances the value is
    provided as a formatted string 
    
    dictionary of { column => type }
    
    The following types are supported:
    
    * int, int32, int64
    * float, float32, float64
    * datetime64[ns] (string of form YYYY-MM-DDThh:mm:ss.nnnnnn)
    * str
    * dict
    """
    name = CharField('name', blank=True, null=True,
                     help_text=('the name of the dataset'))
    """ the name of the dataset (optional)
    
    The dataset name is of format :code:`[path/...]name` where :code:`[path/]`
    is optional and name is the basename of the dataset. Note that the 
    path is not actually a directory path but rather a prefix to the actual
    name. 
    """
    orient = CharField('orient', blank=True, null=True,
                       help_text=('the orientation of the data field. '
                                  'default is dict. optional records. '
                                  'See Pandas.to_dict() for details'))
    """ the orientation of the data field (optional)
    
    see the :code:`data` field. Defaults to dict.
    """

    class Meta:
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get', 'put', 'delete']
        resource_name = 'dataset'
        authentication = ApiKeyAuthentication()

    def restore_filter(self, bundle, name):
        """
        restore filter kwargs for query in om.datasets.get
        """
        # -- get filters as specified on request query args
        fltkwargs = {k: v for k, v in iteritems(bundle.request.GET)
                     if k not in ['orient', 'limit', 'skip', 'page']}
        # -- get dtypes of dataframe and convert filter values
        om = self.get_omega(bundle)
        metadata = om.datasets.metadata(name)
        kind_meta = metadata.kind_meta or {}
        dtypes = kind_meta.get('dtypes')
        # get numpy/python typemap. this is required for Py3 support
        # adopted from https://stackoverflow.com/a/34919415
        np_typemap = {v: getattr(builtins, k)
                      for k, v in np.sctypeDict.items()
                      if k in vars(builtins)}
        for k, v in iteritems(fltkwargs):
            # -- get column name without operator (e.g. x__gt => x)
            col = k.split('__')[0]
            value = urllib.parse.unquote(v)
            dtype = dtypes.get(str(col))
            if dtype:
                # -- get dtyped value and convert to python type
                value = np_typemap.get(getattr(np, dtype, str), str)(value)
                fltkwargs[k] = value
        return fltkwargs

    def obj_get(self, bundle, **kwargs):
        """
        Get a dataset

        HTTP GET :code:`/data/<name>/?<query>`

        :code:`<query>` is optional, when provided any combination of

        *default parameters*

        * :code:`orient=dict|records` see orient field
        * :code:`skip=n` where n is the top n rows to skip
        * :code:`offset=n` where n is the top n rows to skip (same as skip)
        * :code:`limit=n` where n is the top n rows to return, after skip
        * :code:`page=n` where n is the page. same as skip=limit * page

        *filter specification*

        A filter specification is of the form :code:`column__op=value` where
        :code:`column` is the name of a column in the dataframe, and :code:`op`
        is the comparison operator to use to compare to :code:`value`. Note
        that the value is converted to the column's datatype before comparision.
        value should be URI encoded, not quoted.

        Valid operators are:

        * :code:`eq` equality. This is the default operator and specifying
          :code:`column__eq=value` is the same as :code:`column=value`. If the
          name of the column is any of the above default parameters you have
          to use the :code:`eq` operator to distinguish the filter from the
          parameter.
        * :code:`lt` less
        * :code:`gt` greater
        * :code:`le` less or equal
        * :code:`ge` greator or equal

        Note that the :code:`in` operator is currently not supported via the
        REST API yet.
        """
        name = urllib.parse.unquote(kwargs.get('pk'))
        orient = bundle.request.GET.get('orient', 'dict')
        limit = int(bundle.request.GET.get('limit', '50'))
        skip = int(bundle.request.GET.get('skip', '0'))
        offset = int(bundle.request.GET.get('offset', '0'))
        skip = offset or skip
        page = int(bundle.request.GET.get('page', '-1'))
        fltkwargs = self.restore_filter(bundle, name)
        om = self.get_omega(bundle)
        if page > -1:
            skip = limit * page
        obj = om.datasets.getl(name, filter=fltkwargs)
        if hasattr(obj, 'skip'):
            obj = (obj
                   .skip(skip)
                   .head(limit)
                   .value)
        if isinstance(obj, (pd.DataFrame, pd.Series)):
            df = obj
            # get index values as python types to support Py3
            index_values = list(obj.index.astype('O').values)
            index_type = type(obj.index).__name__
            # get data set values as python types to support Py3
            df = df.reset_index(drop=True)
            df.index = df.index.astype('O')
            # convert nan to None
            # https://stackoverflow.com/a/34467382
            data = df.where(pd.notnull(df), None).astype('O').to_dict(orient)
            # build bundle
            if isinstance(data, dict):
                bundle.data = data
            else:
                bundle.data = dict(rows=data)
            bundle.dtypes = df.dtypes.to_dict()
            bundle.index = {
                'type': index_type,
                'values': index_values,
            }
            bundle.orient = orient
        else:
            bundle.data = {'value': obj}
            bundle.dtypes = {'value': type(obj).__name__}
        bundle.name = name
        return bundle

    def obj_update(self, bundle, **kwargs):
        """
        Update a dataset

        HTTP PUT :code:`/data/<name>/?append=0|1`

        :Example:

           > { data: ...,
              dtypes: ...,
              index: ..., }


        :code:`append` is optional and defaults to 1 (true). If true,
           the provided data will be appended to the dataset. If false,
           any existing data will be replaced.
        """
        pk = kwargs.get('pk')
        om = self.get_omega(bundle)
        if 'append' in bundle.request.GET:
            append = isTrue(bundle.request.GET['append'])
        else:
            append = isTrue(bundle.data.get('append', 'true'))
        orient = bundle.data.get('orient', 'columns')
        dtypes = bundle.data.get('dtypes')
        # convert dtypes back to numpy dtypes
        # -- see https://github.com/pandas-dev/pandas/issues/14655#issuecomment-260736368
        if dtypes:
            dtypes = {k: np.dtype(v) for k, v in iteritems(dtypes)}
        # pandas only likes orient = records or columns
        if orient == 'dict':
            orient = 'columns'
        df = pd.DataFrame.from_dict(bundle.data.get('data'),
                                    orient=orient).astype(dtypes)
        index = bundle.data.get('index')
        if index and 'values' in index:
            df.index = index.get('values')
        om.datasets.put(df, pk, append=append)
        return bundle

    def obj_delete(self, bundle, **kwargs):
        """
        Delete a dataset

        HTTP DELETE :code:`/data/<name>/`

        This will delete the dataset. If it is not found HTTP 404 Not found
        is returned.
        """
        pk = kwargs.get('pk')
        om = self.get_omega(bundle)
        try:
            om.datasets.drop(pk)
        except DoesNotExist:
            raise ImmediateHttpResponse(HttpNotFound())
        return bundle

    def detail_uri_kwargs(self, bundle_or_obj):
        # provide the resource_uri
        name = bundle_or_obj.data.get('data', {}).get('name')
        name = name or bundle_or_obj.data.get('name')
        return dict(pk=name)

    def obj_get_list(self, bundle, **kwargs):
        """
        Provide a list of all dataset

        HTTP GET  :code:`/data/<name>/`
        """
        om = self.get_omega(bundle)
        bundle.objs = [
            BundleObj({
                'data': {
                    'name': item.name,
                    'kind': item.kind,
                },
                'dtypes': None,
                'name': None,
                'index': None,
                'orient': None,
            }) for item in om.datasets.list(raw=True)
            if not item.name.startswith('_temp')
        ]
        return bundle.objs
