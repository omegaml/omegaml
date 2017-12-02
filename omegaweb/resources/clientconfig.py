from tastypie.fields import DictField
from tastypie.resources import Resource
from tastypie.authentication import ApiKeyAuthentication
from omegaops import get_client_config


class ClientConfigResource(Resource):
    data = DictField('data')

    class Meta:
        list_allowed_methods = ['get']
        detail_allowed_methods = ['']
        resource_name = 'config'
        authentication = ApiKeyAuthentication()

    def obj_get_list(self, bundle, **kwargs):
        """
        get the configuration
        """
        config = get_client_config(bundle.request.user)
        bundle.data = config or {}
        bundle.pk = config.get('user')
        return [bundle]
