from tastypie.fields import DictField
from tastypie.resources import Resource


class ClientConfigResource(Resource):
    data = DictField('data')

    class Meta:
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get', 'put', 'delete']
        resource_name = 'config'

    def obj_get(self, bundle, **kwargs):
        """
        get the configuration
        """
        
        bundle.data = default_config
        return bundle
