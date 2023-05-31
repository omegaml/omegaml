import logging
from django.http import JsonResponse
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.http import HttpBadRequest
from uuid import uuid4

from omegaml.backends.restapi.asyncrest import truefalse
from omegaml.backends.restapi.job import GenericJobResource
from omegaml.backends.restapi.model import GenericModelResource
from omegaml.backends.restapi.script import GenericScriptResource
from omegaml.backends.restapi.service import GenericServiceResource
from omegaweb.resources.util import get_omega_for_user

logger = logging.getLogger(__name__)


class OmegaResourceMixin(object):
    """
    A Tastypie mixin for omega specifics in resources

    Usage::

        class MyResource(OmegaResourceMixin, Resource):
            ...

        This overrides the create_response_from_resource method,
        which uses an implementation of a GenericResource to actually
        create the response. This allows us to use the same GenericResource
        for both commercial and open source versions of omegaml. To
        this end, this OmegaResourceMixin is a specialization of
        omegaml.backends.restapi.OmegaResourceMixin. We are not using
        a subclass to avoid conflicting dependencies (open source: Flask,
        commercial edition: Django).
    """

    def get_omega(self, bundle_or_request, reset=False):
        """
        Return an Omega instance configured to the request's user
        """
        request = getattr(bundle_or_request, 'request', bundle_or_request)
        if reset or getattr(self, '_omega_instance', None) is None:
            bucket = request.META.get('HTTP_BUCKET')
            qualifier = request.META.get('HTTP_QUALIFIER')
            creds = self._credentials_from_request(request)
            om = get_omega_for_user(request.user, qualifier=qualifier, creds=creds)[bucket]
            self.celeryapp = om.runtime.celeryapp
            # ensure tracking id is set on every request for traceability
            # https://docs.celeryq.dev/en/stable/faq.html?highlight=task_id#can-i-specify-a-custom-task-id
            tracking_id = getattr(request, '_requestid', None) or uuid4().hex
            om.runtime.require(routing=dict(task_id=tracking_id))
            self._omega_instance = om
        return self._omega_instance

    def _credentials_from_request(self, request):
        # get credentials from Meta.authentication, if available
        # -- _authentication_backend is set by tastypie.MultiAuthentication, tastypiex.DeferredAuthentication
        # -- some Authentication classes provide runtime_credentials(), some don't
        # -- TODO move to AuthenticationEnv
        authenticator = getattr(request, '_authentication_backend', self._meta.authentication)
        _default_creds_resolver = lambda request: (request.user.username, request.user.api_key.key)
        creds_resolver = getattr(authenticator, 'runtime_credentials', _default_creds_resolver)
        return creds_resolver(request)

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
        payload = self.deserialize(request, request.body) if request.body else {}
        return query, payload

    def create_response_from_resource(self, request, generic_resource, resource_method, *args, **kwargs):
        """
        Create a response from a resource method

        Args:
            request (Request):
            generic_resource (str): name of the resource
            resource_method (str): name of the resource method
            *args: args to pass to the resource method (ignored)
            **kwargs: kwargs to pass to the resource method, in particular
                pk: the model id

        Returns:
            response: Response
        """
        om = self.get_omega(request)
        model_id = kwargs.get('pk')
        query, payload = self.get_query_payload(request)
        async_body = dict(model=model_id, result='pending')
        try:
            om.start_request(request)
            meth = self._get_resource_method(generic_resource, resource_method)
            result = meth(model_id, query, payload)
            resp = self.create_maybe_async_response(request, result, async_body=async_body)
        except Exception as e:
            msg = dict(message=repr(e))
            raise ImmediateHttpResponse(JsonResponse(msg, status=HttpBadRequest.status_code))
        finally:
            om.close_request()
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

    @property
    def _generic_service_resource(self):
        return GenericServiceResource(self._omega_instance, is_async=getattr(self, 'is_async', False))
