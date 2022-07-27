import base64
import http
import requests
from behave import when, then
from time import sleep
from uuid import uuid4

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
    ctx.feature.password = base64.encodebytes(b"123456").decode('ascii')
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
    # from landingpage.models
    DEPLOY_INITIATED = '0'
    DEPLOY_PENDING = '1'
    DEPLOY_COMPLETED = '5'
    DEPLOY_REMOVED = '8'
    DEPLOY_FAILED = '9'

    # wait until all deployments are done
    # -- deployment is supposed to be done async on user sign up
    api = OmegaAdminApi(ctx.web_url, ctx.api_user, ctx.api_key)
    tries = 10
    while tries:
        sleep(10); tries -= 1
        resp = api.get_deployment_status(ctx.feature.username)
        ctx.assertEqual(resp.status_code, http.HTTPStatus.OK)
        data = resp.json()
        deployments = [item['status'] for item in data['objects']]
        pending = any(v in set(deployments) for v in (DEPLOY_INITIATED, DEPLOY_PENDING))
        if not pending:
            break
    if 'name' in data['objects'][0]:
        # we have the name of the deployment (updated API)
        deployments = [item for item in data['objects'] if item['name'] == 'omegaml']
        ctx.assertEqual(deployments[0]['status'], DEPLOY_COMPLETED)
    else:
        # we don't have the name, at least one of the deployments needs to be ok
        deployments = [item['status'] for item in data['objects']]
        ctx.assertIn(DEPLOY_COMPLETED, deployments)


