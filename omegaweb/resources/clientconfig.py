from django.contrib.auth.models import User
from tastypie.authentication import ApiKeyAuthentication, MultiAuthentication, SessionAuthentication
from tastypie.exceptions import Unauthorized, ImmediateHttpResponse
from tastypie.fields import DictField
from tastypie.http import HttpUnauthorized, HttpBadRequest, HttpNotFound
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
        authentication = MultiAuthentication(ApiKeyAuthentication(),
                                             SessionAuthentication())

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
        # get qualifier from request or default
        # -- qualifier header gets priority (as it is used for authentication)
        # -- allow for query parameter alternative (for testing)
        qualifier = bundle.request.META.get('HTTP_QUALIFIER', 'default')
        qualifier = qualifier or bundle.request.GET.get('qualifier')
        view = isTrue(bundle.request.GET.get('view', False))
        # allow admin users to request some other user's config
        # FIXME only allow query for members in admin's organization
        if bundle.request.user.is_staff:
            if 'user' in bundle.request.GET:
                username = bundle.request.GET.get('user')
                requested_user = User.objects.get(username=username)
        try:
            config = get_client_config(requested_user, qualifier=qualifier, view=view)
        except AssertionError as e:
            raise ImmediateHttpResponse(response=HttpNotFound(str(e)))
        except Exception as e:
            raise ImmediateHttpResponse(response=HttpBadRequest(str(e)))
        bundle.data = config or {}
        bundle.pk = qualifier
        objects = [bundle]
        try:
            objects = self._meta.authorization.read_list(objects, bundle)
        except Unauthorized:
            raise ImmediateHttpResponse(response=HttpUnauthorized())
        return objects
