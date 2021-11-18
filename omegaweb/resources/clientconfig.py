from django.contrib.auth.models import User
from tastypie.authentication import ApiKeyAuthentication
from tastypie.fields import DictField
from tastypie.resources import Resource

from omegaops import get_client_config

isTrue = lambda v: v if isinstance(v, bool) else (
        v.lower() in ['yes', 'y', 't', 'true', '1'])


class ClientConfigResource(Resource):
    data = DictField('data')

    class Meta:
        list_allowed_methods = ['get']
        detail_allowed_methods = []
        resource_name = 'config'
        authentication = ApiKeyAuthentication()

    def obj_get_list(self, bundle, **kwargs):
        """
        get the client configuration for a given user

        By default the user is the authenticated and authorized user. Staff
        users can get other user's configuration by specifying the
        user parameter. Specify the qualifier parameter to get config for
        another qualifier access. Specify the view parameter to return cluster-
        internal host addresses; this should only be used by omega-managed
        services.

        :param user:  (query) the user to get config for
        :param qualifier:  (query) the qualifier to get config for. defaults to 'default'
        :param view: (query) if true return cluster-internal host addresses
        """
        # by default return current user's config
        requested_user = bundle.request.user
        qualifier = bundle.request.GET.get('qualifier', 'default')
        view = isTrue(bundle.request.GET.get('view', False))
        # allow admin users to request some other user's config
        # FIXME only allow query for members in admin's organization
        if bundle.request.user.is_staff:
            if 'user' in bundle.request.GET:
                username = bundle.request.GET.get('user')
                requested_user = User.objects.get(username=username)
        config = get_client_config(requested_user, qualifier=qualifier, view=view)
        bundle.data = config or {}
        bundle.pk = qualifier
        return [bundle]
