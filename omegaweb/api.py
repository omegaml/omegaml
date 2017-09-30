from tastypie.api import Api

from omegaweb.resources import DatasetResource
v1_api = Api('v1')
v1_api.register(DatasetResource())
