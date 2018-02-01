
from mongoengine.errors import DoesNotExist
from six import iteritems
from six.moves import builtins
from tastypie.authentication import ApiKeyAuthentication
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.fields import CharField, DictField
from tastypie.http import HttpNotFound
from tastypie.resources import Resource

from omegaweb.resources.omegamixin import OmegaResourceMixin
from omegaweb.resources.util import isTrue
import pandas as pd
import numpy as np

from .util import BundleObj


class DatasetResource(OmegaResourceMixin, Resource):
    data = DictField('data')
    index = DictField('index', blank=True, null=True)
    dtypes = DictField('dtypes', blank=True, null=True)
    name = CharField('name', blank=True, null=True)
    orient = CharField('orient', blank=True, null=True)

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
                     if k not in ['orient']}
        # -- get dtypes of dataframe and convert filter values
        om = self.get_omega(bundle)
        metadata = om.datasets.metadata(name)
        kind_meta = metadata.kind_meta or {}
        dtypes = kind_meta.get('dtypes')
        # get numpy/python typemap. this is required for Py3 support
        # adopted from https://stackoverflow.com/a/34919415
        np_typemap = {v: getattr(builtins, k)
                      for k, v in np.typeDict.items()
                      if k in vars(builtins)}
        for k, v in iteritems(fltkwargs):
            # -- get column name without operator (e.g. x__gt => x)
            col = k.split('__')[0]
            dtype = dtypes.get(col)
            # -- get dtyped value and convert to python type
            v = np_typemap.get(getattr(np, dtype, str), str)(v)
            fltkwargs[k] = v
        return fltkwargs

    def obj_get(self, bundle, **kwargs):
        """
        Get a dataset
        """
        name = kwargs.get('pk')
        orient = bundle.request.GET.get('orient', 'dict')
        fltkwargs = self.restore_filter(bundle, name)
        om = self.get_omega(bundle)
        obj = om.datasets.get(name, filter=fltkwargs)
        if isinstance(obj, (pd.DataFrame, pd.Series)):
            df = obj
            # get index values as python types to support Py3
            index_values = list(obj.index.astype('O').values)
            index_type = type(obj.index).__name__
            # get data set values as python types to support Py3
            df = df.reset_index(drop=True)
            df.index = df.index.astype('O')
            data = df.astype('O').to_dict(orient)
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
        pk = kwargs.get('pk')
        om = self.get_omega(bundle)
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
        pk = kwargs.get('pk')
        om = self.get_omega(bundle)
        try:
            om.datasets.drop(pk)
        except DoesNotExist:
            raise ImmediateHttpResponse(HttpNotFound())
        return bundle

    def detail_uri_kwargs(self, bundle_or_obj):
        name = bundle_or_obj.data.get('data', {}).get('name')
        name = name or bundle_or_obj.data.get('name')
        return dict(pk=name)

    def obj_get_list(self, bundle, **kwargs):
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
