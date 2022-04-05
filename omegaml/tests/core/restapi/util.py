class RequestsLikeTestClient(object):
    # inspired by https://stackoverflow.com/a/41151251
    def __init__(self, app, is_json=True):
        """ a in-process test client that works like the requests library

        Args:
            app (Flask): the flask app
            is_json (bool): if True, all requests will include a json-valid
               data body and add Accept and Content-Type headers as
               application/json. If False, each request must specify the
               json=<value> parameter where value is a json serializable object
               e.g. dict, list. Defaults to True.

        Usage:
            client = RequestsLikeTestClient()
            client.get(uri, **kwargs)
            client.post(uri, **kwargs)
            client.put(uri, **kwargs)
            client.delete(uri, **kwargs)

            kwargs correspod
        """
        self.client = app.test_client()
        self.headers = None
        self.is_json = is_json

    def make_client_kwargs(self, json=None, auth=None, headers=None, **kwargs):
        self.headers = headers or {}
        if auth:
            auth(self)
        if json is not None or self.is_json:
            from json import dumps
            self.headers.update({
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            })
            # since Werkzeug 2.1, body must always include valid json
            json = json or {}
            kwargs.update(data=dumps(json))
        kwargs.update(headers=self.headers)
        return kwargs

    def wrapper(method):
        def inner(self, *args, **kwargs):
            kwargs = self.make_client_kwargs(**kwargs)
            return getattr(self.client, method)(*args, **kwargs)
        return inner

    get = wrapper('get')
    post = wrapper('post')
    put = wrapper('put')
    delete = wrapper('delete')



