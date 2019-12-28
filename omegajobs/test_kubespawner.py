from unittest import TestCase

from django.contrib.auth.models import User
from tastypie.test import ResourceTestCase

from landingpage.models import ServicePlan
from omegajobs.kubespawner import OmegaKubeSpawner
from omegaml import settings
from omegaops import add_user, add_service_deployment
from omegaweb.tests.util import OmegaResourceTestMixin


class OmegaKubeSpwanerTests(OmegaResourceTestMixin, ResourceTestCase):
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
        self.user.is_staff = True
        self.user.api_key.key = admin_apikey
        self.user.api_key.save()
        self.user.save()
        # setup omega credentials
        self.setup_initconfig()

    def test_makepod_default(self):
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

    def test_makepod_userspecified_values(self):
        spawner = OmegaKubeSpawner(_mock=True)
        spawner.user.name = self.user.username
        # update user config
        jpy_settings = self.deployment.settings['services'].get('jupyter', {})
        jpy_settings['image'] = 'omegaml/omegaml-user-image:latest'
        jpy_settings['namespace'] = 'user-namespace'
        jpy_settings['node_selector'] = f'omegaml.io/user={self.user.username}'
        self.deployment.settings['services']['jupyter'] = jpy_settings
        self.deployment.save()
        # test pod creation
        manifest = spawner.get_pod_manifest().result()
        manifest = manifest.to_dict()
        # ensure pod manifest contains user specified values
        self.assertDictEqual(manifest['spec']['node_selector'], {'omegaml.io/user': self.user.username})
        self.assertEqual(manifest['spec']['containers'][0]['image'], 'omegaml/omegaml-user-image:latest')
        self.assertEqual(spawner.namespace, 'user-namespace')