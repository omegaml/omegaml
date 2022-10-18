from locust import HttpUser, task


class OmegaRestAPIUser(HttpUser):
    @task
    def test_ping(self):
        self.client.get('/healthz')

    @task(5)
    def test_service(self):
        with self.client.get('/api/service/myservice',
                        auth=self.rest_auth) as resp:
            result = resp.json()
            if result.get('data') != 42:
                resp.failure(f'unexpected respohttps://github.com/anchore/syftnse {result}')

    def on_start(self):
        import omegaml as om
        from omegaml.client.auth import AuthenticationEnv
        from omegaml.backends.virtualobj import virtualobj

        @virtualobj
        def myservice(*args, **kwargs):
            return 42

        meta = om.models.put(myservice, 'myservice', replace=True)
        exp = om.runtime.experiment('myexp')
        exp.track('myservice')
        self.om = om
        env = AuthenticationEnv.active()
        self.rest_auth = env.get_restapi_auth(om=om)





