from unittest import TestCase

from django.contrib.auth.models import User
from tastypie.test import ResourceTestCase

from landingpage.models import ServicePlan
from omegajobs.kubespawner import OmegaKubeSpawner
from omegaml import settings
from omegaops import add_user, add_service_deployment


class OmegaKubeSpwanerTests(ResourceTestCase):
    def setUp(self):
        defaults = settings()
        # setup django user
        self.username = username = 'test'
        self.email = email = 'test@omegaml.io'
        self.password = password = 'password'
        self.user = User.objects.create_user(username, email, password)
        self.apikey = self.user.api_key.key
        # set up staff user to query config for above user
        admin_user = defaults.OMEGA_JYHUB_USER
        admin_apikey = defaults.OMEGA_JYHUB_APIKEY
        admin_email = 'admin@omegaml.io'
        self.user = User.objects.create_user(admin_user, admin_email, password)
        self.user.api_key.key = admin_apikey
        self.user.api_key.save()
        # setup omega credentials
        # FIXME refactor to remove dependency to landingpage (omegaweb should
        # have an injectable config module of sorts)
        ServicePlan.objects.create(name='omegaml')
        init_config = {
            'dbname': 'testdb',
            'username': self.user.username,
            'password': 'foobar',
        }
        self.config = add_user(init_config['username'],
                               init_config['password'], dbname=init_config['dbname'])
        add_service_deployment(self.user, self.config)

    def test_makepod(self):
        spawner = OmegaKubeSpawner(_mock=True)
        spawner.user.name = self.user.username
        manifest = spawner.get_pod_manifest().result()
        manifest = manifest.to_dict()
        self.assertTrue('affinity' in manifest['spec'])
        self.assertDictEqual(manifest['spec']['affinity']['node_affinity'],
                             {
                                 'preferred_during_scheduling_ignored_during_execution': None,
                                 'required_during_scheduling_ignored_during_execution': {
                                     'node_selector_terms': [
                                         {'match_expressions': [
                                             {'key': 'omegaml.io/role', 'operator': 'In',
                                              'values': ['worker']}], 'match_fields': None
                                         }
                                     ]}}
                             )
