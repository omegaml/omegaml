from tastypie.exceptions import ImmediateHttpResponse
from tastypie.http import HttpBadRequest

from omegaml.backends.restapi.asyncrest import truefalse
from omegaml.backends.restapi.job import GenericJobResource
from omegaml.backends.restapi.model import GenericModelResource
from omegaml.backends.restapi.script import GenericScriptResource
from omegaweb.resources.util import get_omega_for_user


class OmegaResourceMixin(object):
    """
    A mixin for omega specifics in resources
    """

    def get_omega(self, bundle_or_request, reset=False):
        """
        Return an Omega instance configured to the request's user
        """
        request = getattr(bundle_or_request, 'request', bundle_or_request)
        if reset or getattr(self, '_omega_instance', None) is None:
            bucket = request.META.get('HTTP_BUCKET')
            om = get_omega_for_user(request.user, view=True)[bucket]
            self.celeryapp = om.runtime.celeryapp
            self._omega_instance = om
        return self._omega_instance

    def dispatch(self, request_type, request, **kwargs):
        self._omega_instance = None
        return super().dispatch(request_type, request, **kwargs)

    def pre_cqrs_dispatch(self, request, *args, **kwargs):
        # cqrsapi hook instead of Tastypie Resource.dispatch()
        self._omega_instance = None
        self.is_async = (truefalse(request.GET.get('async', False)) or
                      truefalse(request.META.get('HTTP_ASYNC', False)))
        self._resource_uri = request.path

    def get_query_payload(self, request):
        query = request.GET.dict()
        payload = self.deserialize(request, request.body) if request.body else None
        return query, payload

    def create_response_from_resource(self, request, generic_resource, resource_method, *args, **kwargs):
        self.get_omega(request)
        model_id = kwargs.get('pk')
        query, payload = self.get_query_payload(request)
        async_body = dict(model=model_id, result='pending')
        try:
            meth = self._get_resource_method(generic_resource, resource_method)
            result = meth(model_id, query, payload)
            resp = self.create_maybe_async_response(request, result, async_body=async_body)
        except Exception as e:
            raise ImmediateHttpResponse(HttpBadRequest(str(e)))
        return resp

    def _get_resource_method(self, resource_name, method_name):
        resource = getattr(self, resource_name)
        meth = getattr(resource, method_name)
        return meth

    @property
    def _generic_model_resource(self):
        return GenericModelResource(self._omega_instance, is_async=getattr(self, 'is_async', False))

    @property
    def _generic_job_resource(self):
        return GenericJobResource(self._omega_instance, is_async=getattr(self, 'is_async', False))

    @property
    def _generic_script_resource(self):
        return GenericScriptResource(self._omega_instance, is_async=getattr(self, 'is_async', False))

