from base64 import b64encode
from http import HTTPStatus

import flask
from flask import make_response
from flask_restx import Model, abort, fields
from werkzeug.exceptions import BadRequest, HTTPException

from omegaml.util import MongoEncoder, isTrue, load_class


class StrictModel(Model):
    # To implement a model that supports strict validation
    # on fields, we need to explicitly add into the schema
    # 'additionalProperties: False'
    # See: https://github.com/noirbizarre/flask-restplus/issues/241
    @property
    def _schema(self):
        old = super()._schema
        old['additionalProperties'] = False
        return old


class AnyObject(fields.Wildcard):
    def __init__(self, *args, **kwargs):
        super().__init__(fields.Raw, **kwargs)


class strict:
    # a poor man's stand-in for api.model
    def __init__(self, api):
        self.api = api

    def model(self, name=None, model=None, mask=None, **kwargs):
        # create a strict model and attach to api as in flask-restplus issue #241
        smodel = StrictModel(name, model, mask=mask)
        smodel.__apidoc__.update(kwargs)
        self.api.models[smodel.name] = smodel
        return smodel


class OmegaResourceMixin:
    """
    helper mixin to resolve the request to a configured Omega instance
    """

    max_url_length = 2048

    def __init__(self, *args, **kwargs):
        self._omega_instance = None
        self.is_async = kwargs.pop('is_async', False)
        super().__init__(*args, **kwargs)

    def dispatch_request(self, *args, **kwargs):
        self._omega_instance = None  # always start with a fresh omega instance
        return super().dispatch_request(*args, **kwargs)

    @property
    def _omega(self):
        import omegaml as om

        if self._omega_instance is None:
            bucket = flask.request.headers.get('bucket')
            om = self._omega_instance = om.setup()[bucket]
            try:
                import flask_login

                om.defaults.OMEGA_USERID = flask_login.current_user.get_id()
            except:
                import getpass

                om.defaults.OMEGA_USERID = getpass.getuser()
        return self._omega_instance

    def get_query_payload(self, raw=False, stream=False, streamer=False, is_async=False, **payload_defaults):
        """get query and payload arguments

        Returns the (query, payload, format) tuple as dictionaries to contain a request's parsed query and
        body. The format specifies raw, async, streamer

        """
        from omegaml.server.restapi.resources import omega_api

        query, payload = flask.request.args.to_dict(), None
        if flask.request.is_json:
            payload = omega_api.payload
        elif flask.request.mimetype == 'multipart/form-data':
            payload = {
                **flask.request.form,
                'files': {name: b64encode(f.read()) for name, f in flask.request.files.items()},
            }
        else:
            abort(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        # update for defaults
        # -- eg raw=True
        for k, v in payload_defaults.items():
            payload.setdefault(k, v)
        # format
        format = {
            'raw': raw or payload.get('raw', False),
            'stream': isTrue(stream or payload.get('stream') or query.get('stream')),
            'streamer': streamer or query.get('streamer') or payload.get('streamer'),
            'is_async': isTrue(is_async or query.get('async') or payload.get('async')),
        }
        return query, payload, format

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

    def create_response_from_resource(
        self, generic_resource, resource_method, resource_name, resource_pk, *args, **kwargs
    ):
        query, payload, format_kwargs = self.get_query_payload(**kwargs)
        async_body = {
            resource_name: resource_pk,
            'result': 'pending',
        }
        pattern = rf'{resource_name}/{resource_pk}/{resource_method}/'
        if not self.check_object_authorization(pattern):
            raise BadRequest(f'{pattern} is not available')
        try:
            resource_method = self._get_resource_method(generic_resource, resource_method, **format_kwargs)
            result = resource_method(resource_pk, query, payload)
            resp = self.create_maybe_async_response(result, async_body=async_body, **format_kwargs)
        except Exception as e:
            raise self._build_http_exception(e)
        return resp

    def response(self, body, status, headers, cookies, request=None):
        # request may be required in subclasses of AsyncResponseMixin, e.g. Django tastypie Resource.create_response
        if not cookies:
            return body, status, headers
        resp = make_response((body, status, headers))
        for k, v in (cookies or {}).items():
            resp.set_cookie(k, str(v))
        return resp

    def create_sync_response(self, result, status=None, headers=None, cookies=None, request=None):
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], int):
            body, status = result
            headers = headers or {}
        elif isinstance(result, tuple) and len(result) == 3 and isinstance(result[1], int):
            body, status, headers = result
        elif isinstance(result, tuple) and len(result) == 4 and isinstance(result[1], int):
            body, status, headers, cookies = result
        else:
            body, status, headers = result, status or HTTPStatus.OK, {}
        return self.response(body, int(status), headers, cookies, request=request)

    def _build_http_exception(self, e):
        # build a valid HTTPException from an exception
        # works as follows:
        # - if the exception is an HTTPException, return that
        # - if the exception has a tuple of arguments as (str, int),
        #   assume it is Exception(message, code) => HTTPException(args[0]).code = args[1]
        # - for any other exception, log the traceback and return an error message with a status code of 400
        if isinstance(e, HTTPException):
            return e
        has_status_code = len(e.args) > 1 and isinstance(e.args[1], int)
        if has_status_code:
            message, status_code = e.args
        else:
            # retrieve lowest farme to get the context of the exception
            import logging
            import traceback
            import uuid

            error_id = str(uuid.uuid4())
            tb = traceback.format_exc()
            logging.error(f"Error ID: {error_id}\n{tb}")
            message, status_code = f"{e!r} [Error ID: {error_id}]", BadRequest.code
        exc = HTTPException(message)
        exc.code = status_code
        return exc

    def _get_resource_method(self, resource_name, method_name, **kwargs):
        RESOURCE_REGISTRY = {
            '_generic_model_resource': 'omegaml.backends.restapi.model.GenericModelResource',
            '_generic_script_resource': 'omegaml.backends.restapi.model.GenericScriptResource',
            '_generic_service_resource': 'omegaml.backends.restapi.model.GenericServiceResource',
            '_generic_job_resource': 'omegaml.backends.restapi.model.GenericJobResource',
        }
        resource_cls = load_class(RESOURCE_REGISTRY[resource_name])
        resource = resource_cls(self._omega, **kwargs)
        meth = getattr(resource, method_name)
        return meth

    @property
    def celeryapp(self):
        return self._omega.runtime.celeryapp


class AwareJSONEncoder(MongoEncoder):
    pass
