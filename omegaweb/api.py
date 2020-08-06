from omegaweb.resources.scripts import ScriptResource
from tastypie.api import Api

from omegaweb.resources import DatasetResource, ModelResource
from omegaweb.resources.clientconfig import ClientConfigResource
from omegaweb.resources.jobs import JobResource
from omegaweb.resources.tasks import TaskResource

v1_api = Api('v1')
v1_api.register(DatasetResource())
v1_api.register(ModelResource())
v1_api.register(ClientConfigResource())
v1_api.register(JobResource())
v1_api.register(ScriptResource())
v1_api.register(TaskResource())
