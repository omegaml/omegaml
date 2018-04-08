from django.contrib.auth.models import User
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
        # by default return current user's config
        requested_user = bundle.request.user
        # allow admin users to request some other user's config
        if bundle.request.user.is_staff:
            if 'user' in bundle.request.GET:
                username = bundle.request.GET.get('user')
                requested_user = User.objects.get(username=username)
        config = get_client_config(requested_user)
        bundle.data = config or {}
        bundle.pk = config.get('user')
        return [bundle]
