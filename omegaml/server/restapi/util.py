import flask
from flask_restx import Model, fields
from werkzeug.exceptions import BadRequest, HTTPException

import omegaml as om
from omegaml.util import MongoEncoder


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


class AnyObject(fields.Wildcard):
    def __init__(self, *args, **kwargs):
        super().__init__(fields.Raw, **kwargs)


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


class OmegaResourceMixin(object):
    """
    helper mixin to resolve the request to a configured Omega instance
    """
    max_url_length = 2048

    def __init__(self, *args, **kwargs):
        self._omega_instance = None
        super().__init__(*args, **kwargs)

    def dispatch_request(self, *args, **kwargs):
        self._omega_instance = None  # always start with a fresh omega instance
        return super().dispatch_request(*args, **kwargs)

    @property
    def _omega(self):
        if self._omega_instance is None:
            bucket = flask.request.headers.get('bucket')
            self._omega_instance = om.setup()[bucket]
        return self._omega_instance

    def get_query_payload(self):
        from omegaml.server.restapi.resources import omega_api
        query = flask.request.args.to_dict()
        payload = omega_api.payload or {}
        return query, payload

    def check_object_authorization(self, pattern):
        from omegaml.server.restapi import resource_filter
        if resource_filter:
            if len(pattern) > self.max_url_length:
                # SEC: Avoid ReDoS on admin-provided regular expression
                # -- https://owasp.org/www-community/attacks/Regular_expression_Denial_of_Service_-_ReDoS
                # -- for practical matters we limit the input length
                raise ValueError(f'processing of URLs longer than {self.max_url_length} is not supported')
            if not any(rx.match(pattern) for rx in resource_filter):
                return False
        return True

    def create_response_from_resource(self, generic_resource, resource_method, resource_name, resource_pk, *args,
                                      **kwargs):
        query, payload = self.get_query_payload()
        async_body = {
            resource_name: resource_pk,
            'result': 'pending',
        }
        pattern = rf'{resource_name}/{resource_pk}/{resource_method}/'
        if not self.check_object_authorization(pattern):
            raise BadRequest(f'{pattern} is not available')
        try:
            meth = self._get_resource_method(generic_resource, resource_method)
            result = meth(resource_pk, query, payload)
            resp = self.create_maybe_async_response(result, async_body=async_body, **kwargs)
        except Exception as e:
            raise self._build_http_exception(e)
        return resp

    def _build_http_exception(self, e):
        # build a valid HTTPException from an exception
        # works as follows:
        # - if the exception is an HTTPException, return that
        # - if the exception has a tuple of arguments as (str, int),
        #   assume it is Exception(message, code) => HTTPException(args[0]).code = args[1]
        if isinstance(e, HTTPException):
            return e
        has_status_code = len(e.args) > 1 and isinstance(e.args[1], int)
        if has_status_code:
            message, status_code = e.args
        else:
            message, status_code = repr(e), BadRequest.code
        exc = HTTPException(message)
        exc.code = status_code
        return exc

    def _get_resource_method(self, resource_name, method_name):
        resource = getattr(self, resource_name)
        meth = getattr(resource, method_name)
        return meth

    @property
    def _generic_model_resource(self):
        from omegaml.backends.restapi.model import GenericModelResource
        return GenericModelResource(self._omega, is_async=self.is_async)

    @property
    def _generic_script_resource(self):
        from omegaml.backends.restapi.script import GenericScriptResource
        return GenericScriptResource(self._omega, is_async=self.is_async)

    @property
    def _generic_service_resource(self):
        from omegaml.backends.restapi.service import GenericServiceResource
        return GenericServiceResource(self._omega, is_async=self.is_async)

    @property
    def _generic_job_resource(self):
        from omegaml.backends.restapi.job import GenericJobResource
        return GenericJobResource(self._omega, is_async=self.is_async)

    @property
    def celeryapp(self):
        return self._omega.runtime.celeryapp


class JSONEncoder(MongoEncoder):
    pass
