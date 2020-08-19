"""
implements REST API resource helpers to process async results (promises)

AsyncResponseMixin - a mixin to enable a given Resource to return actual and async results, from the same code
AsyncTaskResourceMixin - a mixin to enable the TaskResource to return status information and resolve results given a task id
"""
from http import HTTPStatus

import celery
import flask
from celery.result import AsyncResult, EagerResult
from flask import request
from werkzeug.exceptions import NotFound

EAGER_RESULTS = {}

truefalse = lambda v: (v if isinstance(v, bool) else
                       any(str(v).lower().startswith(c) for c in ('y', 't', '1')))


class AsyncResponseMixin:
    """
    Mixin to enable a Flask RESTPlus API Resource to return sync and async results with a simple modification

    This implements the async REST API protocol as per http://restcookbook.com/Resources/asynchroneous-operations/
    Specifically for async responses, it returns

        HTTP 202/ACCEPTED
        Location: /location/to/resolve/result

    The same Resource and code can be used to return sync and async results, where the user can request the async version
    by providing the ASYNC=true header, or the ?async=true query argument

    Usage:

        @api.route(...)
        class SomeResource(AsyncResponseMixin, Resource):
            def get(...):
                result = ... # dict or AsyncResult
                async_body = { ... } # dict of data to include if result is AsyncResult
                return self.maybe_async(result, async_body={...})  # would usually return (result, status, headers)

        self.maybe_async() returns, if result is

        * not of type AsyncResult: (body, status, headers), as any usual Resource method
        * of type AsyncResult: (body, status, headers), where
            - status = HTTPStatus.ACCEPTED (202)
            - headers contains a Location header to resolve the result as per self.result_uri
            - a body referencing the AsyncResult task id and the original resources route
              {
                'resource_uri': self.resource_uri,
                'task_id': async.id,
              }

        Clients can request async or sync responses by specifying either of

        * request header ASYNC: true
        * url request query ?async=true

        Your resource method should check the self.is_async property to determine if it should return sync or async
        results. Regardless, self.maybe_async() determines its response by the actual result, not the self.is_async
        value.

        In some cases you may want to process the deferred result returned by the task to return a format in line
        with your REST API specification. A common way to implement task result processing is as follows:

            class SomeResource(...):
                def get(...):
                    async_result = ...
                    async_body = { ... } # dict of data to include if result is AsyncResult
                    result = self.prepare_result(async_result.get()) if not self.is_async else async_result
                    return self.maybe_async(result, async_body=async_body)

                def prepare_result(self, value, **kwargs):
                    return { ... } # actual value

        Note the only difference to the first example is the prepare_result() call and method. The reason for having
        prepare_result() as a separate method is so that it can be reused in the TaskResource to process the deferred
        result value of the AsyncResult. This ensures that the sync and async responses are equivalent, simplifying
        the REST API client processing.

        See the AsyncTaskResourceMixin for details on status checking and deferred result resolving.

    Configuration:

        class SomeResource(AsyncResponseMixin, Resource):
            # specify the client reachable URI to resolve the task, {id} is replaced with task.id
            result_uri = '/api/task/{id}/result'

    """
    # Flask Restplus Resource adapter
    result_uri = '/task/{id}/result'

    def dispatch_request(self, *args, **kwargs):
        # inline with we do not use x-async https://tools.ietf.org/html/rfc6648
        # note in Flask request headers are always as-is and lower-case
        # see https://stackoverflow.com/a/57562733/890242
        self.is_async = (truefalse(request.args.get('async', False)) or
                         truefalse(request.headers.get('async', False)))
        return super().dispatch_request(*args, **kwargs)

    @property
    def resource_uri(self):
        return flask.request.path

    def prep_response(self, result, status=None, headers=None, async_body=None):
        if isinstance(result, AsyncResult):
            if isinstance(result, EagerResult):
                EAGER_RESULTS[result.id] = result
            headers = headers or {}
            headers.update({
                'Location': self.result_uri.format(id=result.id)
            })
            body = async_body or {}
            body.update({
                'resource_uri': self.resource_uri,
                'task_id': result.id,
            })
            status = status or HTTPStatus.ACCEPTED
        else:
            body, status, headers = result, status or HTTPStatus.OK, {}
        return body, int(status), headers

    maybe_async = prep_response
    create_maybe_async_response = prep_response


class AsyncResponseMixinTastypie(AsyncResponseMixin):
    """
    AsyncResourceMixin for Django Tastypie Resources

    Usage:

        class SomeResource(AsyncResponseMixinTastypie, tastypie.Resource):
            class Meta:
                ...
                result_uri = '/api/task/{id}/result'

            def get_detail(self, request, **kwargs):
                result = ... # dict or AsyncResult
                async_body = { ... } # dict of data to include if result is AsyncResult
                # would usually return create_response(...)
                return self.create_maybe_async_response(request, result, async_body={...})

        class TaskResource(AsyncTaskResourceMixin, tastypie.Resource):
            ...
            def get_detail(self, request, **kwargs):
                taskid = kwargs.get('pk') # <pk> is specified in uri by default
                action = kwargs.get('action') # assumes <action> is specified in uri, see Resource.prepend_url
                value, status = self.process_task_action(taskid, action, request=request)
                resp = self.create_response(request, value, status=status)
                return resp
    """

    def dispatch(self, request_type, request, *args, **kwargs):
        # inline with we do not use x-async https://tools.ietf.org/html/rfc6648
        # note in Django request headers are always prefixed with HTTP, uppercase
        # see https://docs.djangoproject.com/en/3.0/ref/request-response/#django.http.QueryDict
        self.is_async = (truefalse(request.GET.get('async', False)) or
                         truefalse(request.META.get('HTTP_ASYNC', False)))
        self._resource_uri = request.path
        return super().dispatch(request_type, request, **kwargs)

    def create_maybe_async_response(self, request, result, status=None, async_body=None):
        # tastypie.create_response drop-in to match AsyncResponseMixin.maybe_async compatibility
        body, status, headers = self.maybe_async(result, status=status, async_body=async_body)
        resp = self.create_response(request, body, status=int(status))
        for k, v in headers.items():
            resp[k] = v
        return resp

    @property
    def result_uri(self):
        return self._meta.result_uri

    @property
    def resource_uri(self):
        return self._resource_uri


class AsyncTaskResourceMixin:
    """
    Mixin to simplify implementation of a TaskResource that returns async results

    Usage:
        To support /task/<id>/status and /task/<id>/result actions implement a resource as follows:

            @api.route('/api/v1/task/<string:taskid>/<string:action>')
            class TaskResource(AsyncTaskResourceMixin, Resource):
                def get(self, taskid, action):
                    # do custom processing or initialization here if needed
                    # any kwargs are passed along as the context argument in subsequent calls
                    return self.process_task_action(taskid, action, request=flask.request)

        With this, the AsyncTaskResourceMixin will take care of /status and /result actions. In particular:

        * /status => self.get_task_status():
            default implementation returns
            {
              'task_id': taskid,
              'status': promise.status,
              'message': message,
            }

        * /result => self.get_task_result():
            default implementation returns
            {
                'task_id': taskid,
                'status': status,
                'response': data
            }

        * where the /result {response: data } is resolved by calling

                promise = self.get_async_result(taskid, context)
                value = self.resolve_promise(promise, context) # calls promise.get()
                resource_method, method_kwargs = self.resolve_resource_method(taskid, context)
                data = resource_method(value, **method_kwargs)

            The default resource_method will simply return the value as is, implemented in self.default_prepare_result()

        * To apply custom value processing, e.g. to support different types of resources or to colocate prep logic with
          the original Resource (instead of duplicating in TaskResource), implement the following additional method:

            def resolve_resource_method(...):
                # return the (callable, kwargs) tuple to format the task results for the actual response
                # the callable should be the same that prepares the result for your sync API response, e.g. prepare_result
                # res_kwargs will be passed on as resource.prepare_result(value, **res_kwargs)
                resourceUri = api.payload.get('resource_uri')
                path, res_kwargs = resolve(resourceUri) # path is the endpoint (str) that matches resource_uri, res_kwargs are the matched kwargs of the route
                resource = <determine resource from path>
                return resource.prepare_result, res_kwargs

          Here the 'resource_uri' is provided in the request payload, referencing the original resource route used to generate
          the async result (i.e. by your SomeResource). The provided resource method will be called as method(value, **kwargs).
    """
    celeryapp = celery.current_app
    is_async = False  # AsyncTaskResource does not support async processing by itself

    def process_task_action(self, taskid, action, **context):
        """
        given a task id and action call the respective get_task_<action> method

        This calls the get_task_<action> method, passing along the caller_args and
        caller_kwargs. The latter should contain any information subsequent

        Args:
            taskid:
            action:
            *caller_args:
            **caller_kwargs:

        Returns:

        """
        promise = self.get_async_result(taskid, context)
        action_meth = getattr(self, 'get_task_{}'.format(action), None)
        if action_meth is None:
            raise ValueError('unknown action {} on task {}'.format(action, taskid))
        try:
            value = action_meth(promise, taskid, context)
            status = HTTPStatus.OK
        except Exception as e:
            value = self.get_task_status(promise, taskid, context, message=str(e))
            status = HTTPStatus.BAD_REQUEST
        return value, int(status)

    def get_task_status(self, promise, taskid, context, message=None):
        result = {
            'task_id': taskid,
            'status': promise.status,
            'message': message,
        }
        return result

    def get_task_result(self, promise, taskid, context):
        # resolve the async result and
        status = promise.status
        value = self.resolve_promise(promise, context)
        result_method, kwargs = self.resolve_resource_method(taskid, context)
        data = result_method(value, **kwargs)
        result = {
            'task_id': taskid,
            'status': status,
            'response': data
        }
        return result

    def get_async_result(self, task_id, context):
        # from a given task id return a AsyncResource as promise
        # hack to allow local testing
        if not getattr(self.celeryapp.conf, 'CELERY_ALWAYS_EAGER'):
            promise = AsyncResult(task_id)
        else:
            promise = EAGER_RESULTS[task_id]
        return promise

    def resolve_promise(self, promise, context):
        # resolve a given AsyncResult, as returned by get_async_result
        if promise.ready():
            try:
                value = promise.get()
            except Exception as error:
                raise ValueError(error)
        else:
            value = None
        return value

    def resolve_resource_method(self, taskid, context):
        # resolve the GenericResoure method to prepare the final result
        # return (callable, kwargs)
        return self.default_prepare_result, {}

    def default_prepare_result(self, value, **kwargs):
        return value


def resolve(uri, method='GET,PUT,POST,DELETE,PATCH'):
    # Flask equivalent of django.urls.resolve
    for m in method.split(','):
        try:
            # see https://werkzeug.palletsprojects.com/en/1.0.x/routing/#werkzeug.routing.MapAdapter.match
            result = flask.current_app.url_map.bind('localhost').match(uri, method=m)
        except:
            pass
        else:
            return result
    raise NotFound("path {} not found".format(uri))
