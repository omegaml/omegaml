from unittest import skip

import tornado
from django.contrib.auth.models import User
from django.test.testcases import TestCase
from kubespawner.spawner import MockObject
from tastypie.test import ResourceTestCaseMixin
from time import sleep
from tornado.testing import AsyncTestCase
from traitlets import Instance
from traitlets.config import Config
from unittest.mock import patch

from omegajobs.kubespawner import OmegaKubeSpawner
from omegaml import settings
from omegaweb.tests.util import OmegaResourceTestMixin


# It looks like AsyncTestCase is not compatible with Django 2.2. After each test, Django will not
# tear down or recreate its database. For that reason, I made this become a regular TestCase.  My
# understanding is that nothing is lost after the change, and all tests still run properly. There
# is a skipped test `test_start()` that does async stuff; but this test also used to be skipped
# under the old Django, so no change here either. If `test_start()` is going to be utilized in the
# future, it might need to be refactored into a separate class.

class OmegaKubeSpawnerTests(OmegaResourceTestMixin, ResourceTestCaseMixin, TestCase):
    def setUp(self):
        super(OmegaKubeSpawnerTests, self).setUp()
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

    def _make_spawner(self):
        user = MockObject()
        user.name = self.user.username
        user.id = self.user.id
        user.url = 'mock_url'
        spawner = OmegaKubeSpawner(_mock=True, user=user)
        return spawner

    def test_makepod_default(self):
        spawner = self._make_spawner()
        manifest = spawner.get_pod_manifest().result()
        manifest = manifest.to_dict()
        self.assertTrue('affinity' in manifest['spec'])
        self.assertDictEqual(manifest['spec']['node_selector'], {'omegaml.io/role': 'worker'})
        # TODO re-add node-affinity / anti-affinity
        # self.assertDictEqual(manifest['spec']['affinity']['node_affinity'],
        #                      {
        #                          'preferred_during_scheduling_ignored_during_execution': None,
        #                          'required_during_scheduling_ignored_during_execution': {
        #                              'node_selector_terms': [
        #                                  {'match_expressions': [
        #                                      {'key': 'omegaml.io/role', 'operator': 'In',
        #                                       'values': ['worker']}], 'match_fields': None
        #                                  }
        #                              ]}}
        #                      )

    def test_makepod_userspecified_jupyter_nodeselector(self):
        # update user config
        jpy_settings = self.deployment.settings['services'].get('jupyter', {})
        jpy_settings['image'] = 'omegaml/omegaml-user-image:latest'
        jpy_settings['namespace'] = 'user-namespace'
        jpy_settings['node_selector'] = f'omegaml.io/role={self.user.username}'
        self.deployment.settings['services']['jupyter'] = jpy_settings
        self.deployment.save()
        # test pod creation
        spawner = self._make_spawner()
        manifest = spawner.get_pod_manifest().result()
        manifest = manifest.to_dict()
        # ensure pod manifest contains user specified values
        self.assertDictEqual(manifest['spec']['node_selector'], {'omegaml.io/role': self.user.username})
        self.assertEqual(manifest['spec']['containers'][0]['image'], 'omegaml/omegaml-user-image:latest')
        self.assertEqual(spawner.namespace, 'user-namespace')

    def test_makepod_volumes_default(self):
        spawner = self._make_spawner()
        spawner.user.name = self.user.username
        # test pod creation
        manifest = spawner.get_pod_manifest().result()
        manifest = manifest.to_dict()
        # ensure pod manifest contains user specified values
        self.assertEqual(manifest['spec']['containers'][0]['volume_mounts'][0]['name'], 'pylib-base')
        self.assertEqual(manifest['spec']['containers'][0]['volume_mounts'][0]['mount_path'], '/app/pylib/base')
        self.assertEqual(manifest['spec']['containers'][0]['volume_mounts'][1]['name'], 'pylib-user')
        self.assertEqual(manifest['spec']['containers'][0]['volume_mounts'][1]['mount_path'], '/app/pylib/user')
        self.assertEqual(manifest['spec']['volumes'][0]['persistent_volume_claim']['claimName'],
                         'pvc-omegaml-pylib-base')
        self.assertEqual(manifest['spec']['volumes'][0]['persistent_volume_claim']['readOnly'], False)
        # see env_local, CONSTANCE_CONFIG.CLUSTER_STORAGE
        if manifest['spec']['volumes'][1]['persistent_volume_claim'] is not None:
            # pvc for pylib user
            self.assertEqual(manifest['spec']['volumes'][1]['persistent_volume_claim']['claimName'],
                             'pvc-omegaml-pylib-user')
            self.assertEqual(manifest['spec']['volumes'][1]['persistent_volume_claim']['readOnly'], False)
        else:
            # hostPath for pylib user
            self.assertEqual(manifest['spec']['volumes'][1]['name'], 'pylib-user')
            self.assertEqual(manifest['spec']['volumes'][1]['host_path']['path'], f"/mnt/local/{self.user.username}")


    def test_makepod_userspecified_jupyter_volumes(self):
        # update user config
        storage_settings = {}
        storage_settings['volumes'] = [dict(name='pylib-user',
                                            persistentVolumeClaim=dict(claimName='worker-user', readOnly=False))]
        storage_settings['volumeMounts'] = [dict(name='pylib-user', mountPath='/app/pylib/user')]
        self.deployment.settings['services']['cluster'] = dict(storage=storage_settings)
        self.deployment.save()
        # test pod creation
        spawner = self._make_spawner()
        manifest = spawner.get_pod_manifest().result()
        manifest = manifest.to_dict()
        # ensure pod manifest contains user specified values
        self.assertEqual(manifest['spec']['containers'][0]['volume_mounts'][0]['name'], 'pylib-user')
        self.assertEqual(manifest['spec']['containers'][0]['volume_mounts'][0]['mount_path'], '/app/pylib/user')
        self.assertEqual(manifest['spec']['volumes'][0]['persistent_volume_claim']['claimName'], 'worker-user')
        self.assertEqual(manifest['spec']['volumes'][0]['persistent_volume_claim']['readOnly'], False)

    def test_makepod_userspecified_jupyter_config(self):
        # update user config
        # https: // zero - to - jupyterhub.readthedocs.io / en / latest / customizing / user - resources.html
        jupyter_config = {}
        jupyter_config['profile_list'] = [
            {
                'display_name': 'base',
                'default': True,
            },
            {
                'display_name': 'training',
                'default': False,
                'kubespawner_override': {
                    'image': 'training/python:label',
                    'cpu_limit': 1,
                    'mem_limit': '512M',
                }
            },
            {
                'display_name': 'gpu',
                'default': False,
                'kubespawner_override': {
                    'image': 'gpu/python:label',
                    'cpu_limit': 1,
                    'mem_limit': '512M',
                }
            }
        ]
        self.deployment.settings['services']['jupyter'] = dict(config=jupyter_config)
        self.deployment.save()
        # test pod creation
        spawner = self._make_spawner()
        # -- simulate user selecting a profile
        spawner._render_options_form(spawner.profile_list)
        spawner.user_options = spawner.options_from_form({'profile': ['training']})
        # note jupyterhub prior to 0.11 worked differently (used index, not slugs, did not need call to load_user_options)
        # see see https://github.com/jupyterhub/kubespawner/commit/ba5171ebb4046d9e82e7f2868b6cc5351c17d2b7#diff-3082573191d96b79e2ec71986d4ef3e2R1823
        spawner.load_user_options()
        # -- build the manifest from user selection
        manifest = spawner.get_pod_manifest().result()
        manifest = manifest.to_dict()
        # ensure pod manifest contains user specified values
        self.assertEqual(manifest['spec']['containers'][0]['image'], 'training/python:label')
        # -- simulate user selecting the oteher profile
        spawner._render_options_form(spawner.profile_list)
        spawner.user_options = spawner.options_from_form({'profile': ['gpu']})
        spawner.load_user_options()
        # -- build the manifest from user selection
        manifest = spawner.get_pod_manifest().result()
        manifest = manifest.to_dict()
        # ensure pod manifest contains user specified values
        self.assertEqual(manifest['spec']['containers'][0]['image'], 'gpu/python:label')
        # check reset profile list works
        # -- this tests kubespawner._apply_omega_configs, call to _render_options_form
        spawner.profile_list = []
        prev_options_form = spawner.options_form
        spawner.options_form = spawner._render_options_form(spawner.profile_list)
        post_options_form = spawner.options_form
        self.assertNotEqual(prev_options_form, post_options_form)

    @skip("use this for interative testing only")
    @tornado.testing.gen_test()
    def test_start(self):
        user = MockObject()
        user.name = self.user.username
        user.id = 'mock_id'
        user.url = 'mock_url'
        hub = MockObject()
        hub.public_host = 'localhost'
        hub.api_url = '/api'
        hub.base_url = '/hub'

        spawner = OmegaKubeSpawner(user=user, hub=hub, _mock=False)
        spawner.user = user
        spawner.events_enabled = False

        future = yield spawner.start()
        while not future.done():
            print("waiting")
            sleep(1)
        print("done")


    def test_startup_failed_load_config(self):
        # https://github.com/omegaml/omegaml-enterprise/issues/254
        with patch('omegajobs.spawnermixin.get_user_config_from_api',
                   side_effect=AssertionError('problem')) as mock:
            config = Instance(Config, (), {})
            config._has_section = lambda *args : False
            try:
                spawner = self._make_spawner()
                spawner._load_config(config)
            except:
                raised = True
            else:
                raised = False
            self.assertFalse(raised)


