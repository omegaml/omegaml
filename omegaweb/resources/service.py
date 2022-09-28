"""
REST API to jobs
"""
from tastypie.authentication import ApiKeyAuthentication, MultiAuthentication, SessionAuthentication
from tastypie.resources import Resource

from omegaml.backends.restapi.asyncrest import AsyncResponseMixinTastypie
from omegaweb.resources.omegamixin import OmegaResourceMixin
from tastypiex.cqrsmixin import CQRSApiMixin, cqrsapi


class ServiceResource(CQRSApiMixin, OmegaResourceMixin, AsyncResponseMixinTastypie, Resource):
    """
    Service resource implements the REST API to models, jobs, scripts that have a signature
    """

    class Meta:
        list_allowed_methods = []
        detail_allowed_methods = ['get', 'post', 'put', 'delete']
        resource_name = 'service'
        authentication = MultiAuthentication(ApiKeyAuthentication(),
                                             SessionAuthentication())
        result_uri = '/api/v1/task/{id}/result'
        resource_handler = '_generic_service_resource'

    def get_detail(self, request, *args, **kwargs):
        # /service/
        return self.create_response_from_resource(request, self._meta.resource_handler, 'get', *args, **kwargs)

    def put_detail(self, request, *args, **kwargs):
        # /service/
        return self.create_response_from_resource(request, self._meta.resource_handler, 'put', *args, **kwargs)

    def delete_detail(self, request, *args, **kwargs):
        # /service/
        return self.create_response_from_resource(request, self._meta.resource_handler, 'delete', *args, **kwargs)

    def post_detail(self, request, *args, **kwargs):
        # /service/
        return self.create_response_from_resource(request, self._meta.resource_handler, 'post', *args, **kwargs)

    @cqrsapi(allowed_methods=['get'])
    def doc(self, request, *args, **kwargs):
        # /service/predict/
        return self.create_response_from_resource(request, self._meta.resource_handler, 'doc', *args, **kwargs)

    @cqrsapi(allowed_methods=['post'])
    def predict(self, request, *args, **kwargs):
        # /service/predict/
        return self.create_response_from_resource(request, self._meta.resource_handler, 'predict', *args, **kwargs)

    @cqrsapi(allowed_methods=['post'])
    def predict_proba(self, request, *args, **kwargs):
        # /service/predict_proba/
        return self.create_response_from_resource(request, self._meta.resource_handler, 'predict_proba', *args,
                                                  **kwargs)

    @cqrsapi(allowed_methods=['post'])
    def run(self, request, *args, **kwargs):
        # /service/run/
        return self.create_response_from_resource(request, self._meta.resource_handler, 'run', *args, **kwargs)
