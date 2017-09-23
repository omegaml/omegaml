from tastypie.api import Api

from omegaweb.resources import ObjectResource
v1_api = Api('v1')
v1_api.register(ObjectResource())
