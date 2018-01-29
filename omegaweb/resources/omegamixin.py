from omegaweb.resources.util import get_omega_for_user


class OmegaResourceMixin(object):

    """
    A mixin for omega specifics in resources
    """

    def get_omega(self, bundle_or_request):
        """
        Return an Omega instance configured to the request's user
        """
        request = getattr(bundle_or_request, 'request', bundle_or_request)
        return get_omega_for_user(request.user)
