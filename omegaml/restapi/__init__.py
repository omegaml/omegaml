from omegaml.restapi.util import strict, AnyObject
from .app import create_app

# list of regex to filter available resources in format
#   resource/name/action
#   e.g. model/.*/.* => allow all models
#   e.g. model/foo/predict => allow only prediction
# only regex that match at least one regex can succeed
# empty list means all objects and actions are allowed
# see OmegaResourceMixin.check_object_authorization()
resource_filter = []
