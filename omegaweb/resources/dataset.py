from mongoengine.errors import DoesNotExist
from six import iteritems
from tastypie.authentication import ApiKeyAuthentication
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.fields import CharField, DictField
from tastypie.http import HttpNotFound
from tastypie.resources import Resource

import numpy as np
from omegaml import Omega
from omegaops import get_client_config
from omegaweb.resources.util import isTrue
import pandas as pd

from .util import BundleObj


class DatasetResource(Resource):
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
        for k, v in iteritems(fltkwargs):
            # -- get column name without operator (e.g. x__gt => x)
            dtype = dtypes.get(k.split('__')[0])
            v = getattr(np, dtype, str)(v)
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
            data = df.reset_index(drop=True).to_dict(orient)
            if isinstance(data, dict):
                bundle.data = data
            else:
                bundle.data = dict(rows=data)
            bundle.dtypes = df.dtypes.to_dict()
            bundle.index = {
                'type': type(obj.index).__name__,
                'values': list(obj.index),
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
        df = pd.DataFrame.from_dict(bundle.data.get('data'), orient=orient)
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
        ]
        return bundle.objs

    def get_omega(self, bundle_or_request):
        """
        Return an Omega instance configured to the request's user
        """
        request = getattr(bundle_or_request, 'request', bundle_or_request)
        user = request.user
        config = get_client_config(user)
        mongo_url = config.get('OMEGA_MONGO_URL')
        om = Omega(mongo_url=mongo_url)
        return om
