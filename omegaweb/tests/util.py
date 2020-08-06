import json
from http import HTTPStatus

from landingpage.models import ServicePlan
from omegaops import add_user, add_service_deployment


class OmegaResourceTestMixin:
    def setup_initconfig(self):
        # note this is specific to the current config version
        init_config = {
            'version': 'v2',
            'qualifiers': {
                'default': {
                    'mongodbname': 'testdb',
                    'mongousername': self.user.username,
                    'mongopassword': 'jk3XVEpbpevN4BgtEbmcCpVM24gc7RVB',
                }
            }
        }
        ServicePlan.objects.create(name='omegaml')
        user_config = init_config['qualifiers']['default']
        self.config = add_user(user_config['mongousername'],
                               user_config['mongopassword'],
                               dbname=user_config['mongodbname'])
        self.deployment = add_service_deployment(self.user, self.config)

    @property
    def _async_headers(self):
        return dict(HTTP_ASYNC=True)

    def _check_async(self, resp):
        # check resp is async, then retrieve actual result as type TaskOutput
        self.assertHttpAccepted(resp)
        data = self.deserialize(resp)
        location = resp['Location']
        self.assertRegexpMatches(location, r'http://testserver/api/v1/task/.*/result')
        # check we can get back the actual result
        resp = self.api_client.get(location.replace('http://testserver', ''), data={
            'resource_uri': data.get('resource_uri'),
        }, authentication=self.get_credentials())
        data = self.deserialize(resp)
        self.assertIn('status', data)
        self.assertIn(data['task_id'], location)
        if resp.status_code == HTTPStatus.OK:
            msg = "expected status_code == OK, got {} with data {}".format(resp.status_code, data)
            self.assertEqual(data['status'], 'SUCCESS', msg)
        else:
            msg = "expected status_code != OK, got {} with data {}".format(resp.status_code, data)
            self.assertEqual(data['status'], 'FAILURE', msg)
        return resp


def assertDictEqualJSON(self, d, filename):
    with open(filename, 'r') as fin:
        self.assertDictEqual(d, json.load(fin))
