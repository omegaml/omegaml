from tastypie.api import Api

from omegaweb.resources import DatasetResource, ModelResource
v1_api = Api('v1/objects')
v1_api.register(DatasetResource())
v1_api.register(ModelResource())
