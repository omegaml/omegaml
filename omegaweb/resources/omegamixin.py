class OmegaResourceMixin(object):

    """
    A mixin for omega specifics in resources
    """

    def get_omega(self, bundle_or_request):
        """
        Return an Omega instance configured to the request's user
        """
        from omegaml import Omega
        from omegaops import get_client_config

        request = getattr(bundle_or_request, 'request', bundle_or_request)
        user = request.user
        config = get_client_config(user)
        mongo_url = config.get('OMEGA_MONGO_URL')
        om = Omega(mongo_url=mongo_url,
                   celeryconf=config.get('OMEGA_CELERY_CONFIG'))
        return om
