import base64
import http
from uuid import uuid4

import requests
import six
from behave import when, then

from omegaml.client.auth import OmegaRestApiAuth


class OmegaAdminApi:
    def __init__(self, url, user, apikey):
        self.url = url
        self.user = user
        self.apikey = apikey

    def service_url(self, name, pk=None):
        url = "{self.url}/admin/api/v2/service/{name}".format(**locals())
        return self.fqurl(url + '{}/'.format(pk) if pk else url)

    def auth_url(self, name, pk=None):
        url = "{self.url}/admin/api/v2/auth/{name}/".format(**locals())
        return self.fqurl(url + '{}/'.format(pk) if pk else url)

    def credentials(self, user=None, apikey=None):
        user = user or self.user
        apikey = apikey or self.apikey
        return OmegaRestApiAuth(self.user, self.apikey)

    def fqurl(self, url):
        if not url.startswith(self.url):
            sep = '/' if not self.url.endswith('/') else ''
            url = '{self.url}{sep}{url}'.format(**locals())
        return url

    def signup(self, email, password):
        data = {
            "email": email,
            "first_name": "First",
            "last_name": "Last",
            "password": password,
        }
        resp = requests.post(self.auth_url('signup'), json=data,
                             auth=self.credentials())
        return resp

    def get_deployment_status(self, email):
        url = '{}?user__email={}'.format(self.service_url('deployment'), email)
        return requests.get(self.fqurl(url), auth=self.credentials())

    def query(self, url):
        return requests.get(self.fqurl(url), auth=self.credentials())


@when("we signup a new user (api)")
def api_signup_user(ctx):
    api = OmegaAdminApi(ctx.web_url, ctx.api_user, ctx.api_key)
    # we set this for subsequent steps to use this data
    ctx.feature.username = '{}@omegaml.io'.format(uuid4().hex)
    ctx.feature.password = base64.encodebytes(six.b("123456")).decode('ascii'),
    # sign up
    resp = api.signup(ctx.feature.username, ctx.feature.password)
    ctx.assertEqual(resp.status_code, http.HTTPStatus.CREATED)
    # get user data back and verify
    data = resp.json()
    resp = api.query(data['resource_uri'])
    ctx.assertEqual(resp.status_code, http.HTTPStatus.OK)
    data = resp.json()
    ctx.assertEqual(data['email'], ctx.feature.username)


@then("the service is deployed (api)")
def api_service_deployed(ctx):
    api = OmegaAdminApi(ctx.web_url, ctx.api_user, ctx.api_key)
    resp = api.get_deployment_status(ctx.feature.username)
    ctx.assertEqual(resp.status_code, http.HTTPStatus.OK)
    data = resp.json()
    DEPLOY_COMPLETED = '5' # from landingpage.models
    ctx.assertEqual(data['objects'][0]['status'], DEPLOY_COMPLETED)


