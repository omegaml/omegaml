from tastypie.bundle import Bundle
from tastypie.fields import CharField, DictField
from tastypie.resources import Resource

import omegaml as om
import pandas as pd


class BundleObj(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


isTrue = lambda v: v.lower() in ['yes', 'y', 't', 'true', '1']


class ObjectResource(Resource):
    data = DictField('data')
    dtypes = DictField('dtypes', readonly=True, blank=True, null=True)

    class Meta:
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get', 'put', 'delete']
        resource_name = 'object'

    def obj_get(self, bundle, **kwargs):
        orient = bundle.request.GET.get('orient', 'dict')
        obj = om.datasets.get(kwargs.get('pk'))
        if isinstance(obj, (pd.DataFrame, pd.Series)):
            df = obj
            bundle.data = df.to_dict(orient)
            bundle.dtypes = df.dtypes.to_dict()
        else:
            bundle.data = {'value': obj}
            bundle.dtypes = {'value': type(obj).__name__}
        return bundle

    def obj_update(self, bundle, **kwargs):
        pk = kwargs.get('pk')
        append = isTrue(bundle.data.get('append', 'true'))
        orient = bundle.data.get('orient', 'columns')
        df = pd.DataFrame.from_dict(bundle.data.get('data'), orient=orient)
        om.datasets.put(df, pk, append=append)
        return bundle

    def obj_delete(self, bundle, **kwargs):
        pk = kwargs.get('pk')
        om.datasets.drop(pk)
        return bundle

    def detail_uri_kwargs(self, bundle_or_obj):
        return dict(pk=bundle_or_obj.data.get('data', {}).get('name'))

    def obj_get_list(self, bundle, **kwargs):
        bundle.objs = [
            BundleObj({
                'data': {
                    'name': item.name,
                    'kind': item.kind,
                },
                'dtypes': None
            }) for item in om.datasets.list(raw=True)
        ]
        return bundle.objs
