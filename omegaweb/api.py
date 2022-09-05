from django.urls import re_path, include

from omegaweb.resources.scripts import ScriptResource
from tastypie.api import Api

from omegaweb.resources import DatasetResource, ModelResource
from omegaweb.resources.clientconfig import ClientConfigResource
from omegaweb.resources.jobs import JobResource
from omegaweb.resources.service import ServiceResource
from omegaweb.resources.tasks import TaskResource
from omegaweb.resources.util import TopLevelApi

v1_api = Api('v1')
v1_api.register(DatasetResource())
v1_api.register(ModelResource())
v1_api.register(ClientConfigResource())
v1_api.register(JobResource())
v1_api.register(ScriptResource())
v1_api.register(TaskResource())
# we expose service resource as /api/v1/service and /api/service
# rationale: this is user-defined, and /v1/ does not make sense in this case
# however in light of consistency, we also provide /v1/
v1_api.register(ServiceResource())
service_api = TopLevelApi('service')
service_api.register(ServiceResource())
