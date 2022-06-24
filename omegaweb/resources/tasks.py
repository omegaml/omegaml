import re

from django.urls import resolve
from tastypie.authentication import ApiKeyAuthentication, MultiAuthentication, SessionAuthentication
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.fields import DictField, CharField
from tastypie.http import HttpNotFound
from tastypie.resources import Resource

from omegaml.backends.restapi.asyncrest import AsyncTaskResourceMixin
from tastypiex.jwtauth import JWTAuthentication
from omegaweb.resources.omegamixin import OmegaResourceMixin
from tastypiex.cqrsmixin import CQRSApiMixin, cqrsapi


class TaskResource(CQRSApiMixin, OmegaResourceMixin, AsyncTaskResourceMixin, Resource):
    task_id = CharField('task_id', blank=True, null=True,
                        help_text='the task id')
    status = CharField('status', blank=True, null=True,
                       help_text='the task status')
    response = DictField('response', blank=True, null=True,
                         help_text='the task result as in sync REST API')

    class Meta:
        list_allowed_methods = []
        detail_allowed_methods = ['get', 'delete']
        resource_name = 'task'
        authentication = MultiAuthentication(ApiKeyAuthentication(),
                                             JWTAuthentication(),
                                             SessionAuthentication())

    @cqrsapi(allowed_methods=['get'])
    def status(self, request, *args, **kwargs):
        self.get_omega(request)
        taskid = kwargs.get('pk')
        action = 'status'
        value, status = self.process_task_action(taskid, action, request=request)
        resp = self.create_response(request, value, status=status)
        return resp

    @cqrsapi(allowed_methods=['get'])
    def result(self, request, *args, **kwargs):
        self.get_omega(request)
        taskid = kwargs.get('pk')
        action = 'result'
        value, status = self.process_task_action(taskid, action, request=request)
        resp = self.create_response(request, value, status=status)
        return resp

    def resolve_resource_method(self, task_id, context, *args, **kwargs):
        # implements AsyncTaskResourceMixin.resolve_resource_method
        # this maps a tasks resource_uri to a resource method to prepare the final result
        request = context['request']
        resourceUri = request.GET.get('resource_uri')
        res_match = resolve(resourceUri)
        # specify original resource URI and how to resolve using a GenericResource
        # { uri-regexp => (resource-property, resource-method, { uri-kw => method-kw }) }
        # where
        #    uri-regexp => is the regex matching the resource_uri for a given mapping to apply
        #    resource-property: the self.property that returns a GenericResource instance
        #    resource-method: the GenericResource.method to prepare the final result from the task result value
        #    uri-kw: the kw given in the API uri, method-kw is the equivalent kw on the resource-method
        # If no resource-uri match is found, HttpNotFound is raised to avoid unknown tasks from being resolved
        # Typically the resource-property is implemented by OmegaResourceMixin
        URI_METHOD_MAP = {
            r"/api/.*/model/.*/.*/?$": ('_generic_model_resource', 'prepare_result', {'pk': 'model_id'}),
            r'/api/.*/job/.*/run/?$': ('_generic_job_resource', 'prepare_result_from_run', {'pk': 'job_id'}),
            r'/api/.*/script/.*/run/?$': ('_generic_script_resource', 'prepare_result_from_run', {'pk': 'script_id'}),
        }
        for regexp, specs in URI_METHOD_MAP.items():
            if re.match(regexp.replace(r'/', r'\/'), resourceUri):
                resource_name, method_name, kwargs_map = specs
                meth = self._get_resource_method(resource_name, method_name)
                meth_kwargs = {kwargs_map.get(k): res_match.kwargs.get(k) for k in res_match.kwargs.keys() if k in kwargs_map}
                return meth, meth_kwargs
        raise ImmediateHttpResponse(HttpNotFound('unknown resource {}'.format(resourceUri)))
