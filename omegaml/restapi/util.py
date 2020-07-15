import json
from datetime import datetime

from flask_restplus import Model


class StrictModel(Model):
    # To implement a model that supports strict validation
    # on fields, we need to explicitly add into the schema
    # 'additionalProperties: False'
    # See: https://github.com/noirbizarre/flask-restplus/issues/241
    @property
    def _schema(self):
        old = super(StrictModel, self)._schema
        old['additionalProperties'] = False
        return old


class strict(object):
    # a poor man's stand-in for api.model
    def __init__(self, api):
        self.api = api

    def model(self, name=None, model=None, mask=None, **kwargs):
        # create a strict model and attach to api as in flask-restplus issue #241
        smodel = StrictModel(name, model, mask=mask)
        smodel.__apidoc__.update(kwargs)
        self.api.models[smodel.name] = smodel
        return smodel


