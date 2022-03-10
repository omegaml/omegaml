import flask


class RequestsLikeTestClient(object):
    # inspired by https://stackoverflow.com/a/41151251
    def __init__(self, app):
        self.client = app.test_client()
        self.headers = None

    def make_client_kwargs(self, json=None, auth=None, headers=None, **kwargs):
        self.headers = headers or {}
        if auth:
            auth(self)
        if json:
            from json import dumps
            self.headers.update({
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            })
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



