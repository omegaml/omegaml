import json

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


def assertDictEqualJSON(self, d, filename):
    with open(filename, 'r') as fin:
        self.assertDictEqual(d, json.load(fin))
