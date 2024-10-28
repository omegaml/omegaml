import time

from locust import HttpUser, task, User


class OmegaRestAPIUser(HttpUser):
    @task
    def test_ping(self):
        self.client.get('/healthz')

    @task(5)
    def test_service(self):
        with self.client.get('/api/service/myservice',
                             auth=self.rest_auth, catch_response=True) as resp:
            result = resp.json()
            if result.get('data') != 42:
                resp.failure(ValueError('wrong response'))

    def on_start(self):
        import omegaml as om
        from omegaml.client.auth import AuthenticationEnv
        from omegaml.backends.virtualobj import virtualobj

        self.om = om.setup(view=False)

        @virtualobj
        def myservice(*args, **kwargs):
            return 42

        if not om.models.exists('myservice'):
            meta = om.models.put(myservice, 'myservice', replace=True)
            exp = om.runtime.experiment('myexp')
            exp.track('myservice')

        env = AuthenticationEnv.active()
        self.rest_auth = env.get_restapi_auth(om=om, qualifier='default')


class measure:
    """ a generic measurement context for locust

    Measure anything with locust, the modern load testing framework.

    Locust is a great tool to perform variable load testing, and it
    works out of the box for Http-type systems. For other systems, it
    requires the implementation of a custom User and Client class. With
    measure(), this is no longer necessary. Just write your code and
    stick it into a "with measure()" block:

    Usage:
        # in your user class
        @task
        def mytask(self):
            with measure(self) as m:
                ... your code
                if failed:
                    m.failure()
                else:
                    m.success()
    """
    # adopted from https://docs.locust.io/en/stable/testing-other-systems.html
    def __init__(self, user, name=None, context=None):
        import inspect
        # https://docs.python.org/3/library/inspect.html#inspect.FrameInfo
        self.caller = user or self
        self.name = name or inspect.stack()[1][3]
        self.response = None
        self.context = context

    def success(self, response=None):
        self.response = response

    def failure(self, response):
        self.response = response
        raise ValueError(response)

    def __enter__(self):
        # https://stackoverflow.com/a/28185561/890242
        import time

        self.start_rt = time.time()
        self.start_pc = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        stop_rt = time.time()
        stop_pc = time.perf_counter()
        context = getattr(self.caller, 'context', lambda: self.context)()
        request_meta = {
            'request_type': 'locust',
            'name': self.name,
            'start_time': self.start_rt,
            'stop_time': stop_rt,
            'response': self.response,
            'response_length': len(self.response) if hasattr(self, '__len__') else 0,
            'response_time': (stop_pc - self.start_pc) * 1000,
            'exception': exc_val,
            'context': context,
        }
        self.caller.environment.events.request.fire(**request_meta)
        return request_meta['response']


class OtherUser(User):

    @task
    def test_ping(self):
        om = self.om
        with measure(self):
            om.runtime.require('default').ping()

    def on_start(self):
        import omegaml as om
        self.om = om.setup(view=False)
        self.om.runtime.ping()




