from unittest import TestCase

from mock import patch
from six import StringIO

from omegaml.defaults import update_from_config, update_from_obj, update_from_dict


class BareObj(object):
    pass


class ConfigurationTests(TestCase):
    def setUp(self):
        self.defaults = {
            'OMEGA_MONGO_URL': 'foo'
        }

    def test_update_from_configfile(self):
        """
        Test updates from config file works
        """
        data = """
        OMEGA_MONGO_URL: updated-foo
        NOTOMEGA_VALUE: some other value
        """
        update_from_config(vars=self.defaults, config_file=StringIO(data))
        self.assertIn('OMEGA_MONGO_URL', self.defaults)
        self.assertEqual(self.defaults['OMEGA_MONGO_URL'], 'updated-foo')
        self.assertNotIn('NOTOMEGA_VALUE', self.defaults)

    def test_update_from_obj(self):
        data = BareObj()
        data.OMEGA_MONGO_URL = 'updated-foo'
        update_from_obj(data, self.defaults)
        self.assertIn('OMEGA_MONGO_URL', self.defaults)
        self.assertEqual(self.defaults['OMEGA_MONGO_URL'], 'updated-foo')
        self.assertNotIn('NOTOMEGA_VALUE', self.defaults)

    def test_update_from_obj_nested(self):
        data = BareObj()
        data.OMEGA_CELERY_CONFIG = {
            'TASK_SERIALIZER': 'json',
        }
        self.defaults['OMEGA_CELERY_CONFIG'] = {
            'RESULT_SERIALIZER': 'pickle',
            'TASK_SERIALIZER': 'pickle',
        }
        update_from_obj(data, self.defaults)
        self.assertEqual(self.defaults['OMEGA_CELERY_CONFIG']['RESULT_SERIALIZER'], 'pickle')
        self.assertEqual(self.defaults['OMEGA_CELERY_CONFIG']['TASK_SERIALIZER'], 'json')

    def test_update_obj_from_obj_nested(self):
        data = BareObj()
        data.OMEGA_CELERY_CONFIG = {
            'TASK_SERIALIZER': 'json',
        }
        defaults = BareObj()
        defaults.OMEGA_CELERY_CONFIG = {
            'RESULT_SERIALIZER': 'pickle',
            'TASK_SERIALIZER': 'pickle',
        }
        update_from_obj(data, defaults)
        self.assertEqual(defaults.OMEGA_CELERY_CONFIG['RESULT_SERIALIZER'], 'pickle')
        self.assertEqual(defaults.OMEGA_CELERY_CONFIG['TASK_SERIALIZER'], 'json')

    def test_update_from_dict(self):
        data = {
            'OMEGA_MONGO_URL': 'updated-foo'
        }
        update_from_dict(data, self.defaults)
        self.assertIn('OMEGA_MONGO_URL', self.defaults)
        self.assertEqual(self.defaults['OMEGA_MONGO_URL'], 'updated-foo')
        self.assertNotIn('NOTOMEGA_VALUE', self.defaults)

    def test_config_from_apikey(self):
        """
        Test an Omega instance can be created from user specific configs
        """
        import omegaml as om
        from omegaml.util import settings
        # check we get default without patching
        from omegaml import _base_config as _real_base_config
        with patch('omegaml._base_config', new=BareObj) as defaults:
            # link callbacks used by get_omega_from_api_key
            _real_base_config.update_from_obj(_real_base_config, attrs=defaults)
            defaults.update_from_dict = _real_base_config.update_from_dict
            defaults.update_from_config = _real_base_config.update_from_config
            defaults.load_user_extensions = lambda *args, **kwargs: None
            defaults.load_framework_support = lambda *args, **kwargs: None
            setup = om.setup
            defaults.MY_OWN_SETTING = 'foo'
            settings(reload=True)
            om = om.setup()
            self.assertEqual(om.defaults.MY_OWN_SETTING, 'foo')
            # reset om.datasets to restored defaults
            om = setup()
            self.assertNotEqual(om.datasets.mongo_url, 'foo')
        # now test we can change the default through config
        # we patch the actual api call to avoid having to set up the user db
        # the objective here is to test get_omega_from_apikey
        with patch('omegaml.client.userconf.get_user_config_from_api') as mock:
            mock.return_value = {
                'objects': [
                    {
                        'data': {
                            'OMEGA_MONGO_URL': 'updated-foo',
                            'OMEGA_MY_OWN_SETTING': 'updated-foo',
                            'OMEGA_CELERY_CONFIG': {
                                'TEST_SETTING': 'pickle',
                            }
                        }
                    }
                ]
            }
            with patch('omegaml._base_config', new=BareObj) as defaults:
                from omegaml.client.userconf import get_omega_from_apikey
                # link callbacks used by get_omega_from_api_key
                _real_base_config.update_from_obj(_real_base_config, attrs=defaults)
                defaults.update_from_dict = _real_base_config.update_from_dict
                defaults.load_user_extensions = lambda *args, **kwargs: None
                defaults.load_framework_support = lambda *args, **kwargs: None
                defaults.OMEGA_MY_OWN_SETTING = 'foo'
                om = get_omega_from_apikey('foo', 'bar')
                self.assertEqual(om.defaults.OMEGA_MY_OWN_SETTING, 'updated-foo')
                self.assertEqual(om.datasets.mongo_url, 'updated-foo')
                self.assertEqual(om.defaults.OMEGA_CELERY_CONFIG['TEST_SETTING'], 'pickle')
                # test that all default values are still there, i.e. the OMEGA_CELERY_CONFIG was updated, not replaced
                for real_k, real_v in _real_base_config.OMEGA_CELERY_CONFIG.items():
                    self.assertIn(real_k, om.defaults.OMEGA_CELERY_CONFIG)
        # restore defaults
        defaults = settings(reload=True)
        om = setup()
        self.assertNotEqual(om.datasets.mongo_url, 'foo')

    def test_user_extensions_config(self):
        # check we get default without patching
        from omegaml.util import settings
        from omegaml import _base_config as _real_base_config
        with patch('omegaml.client.userconf.get_user_config_from_api') as mock:
            mock.return_value = {
                'objects': [
                    {
                        'data': {
                            "OMEGA_USER_EXTENSIONS": {
                                "OMEGA_STORE_BACKENDS": {
                                    "test.backend": 'omegaml.backends.npndarray.NumpyNDArrayBackend'
                                }}}}]
            }
            with patch('omegaml._base_config', new=BareObj) as defaults:
                from omegaml.client.userconf import get_omega_from_apikey
                # link callbacks used by get_omega_from_api_key
                _real_base_config.update_from_obj(_real_base_config, attrs=defaults)
                defaults.update_from_dict = _real_base_config.update_from_dict
                defaults.update_from_config = _real_base_config.update_from_config
                defaults.load_user_extensions = _real_base_config.load_user_extensions
                defaults.load_framework_support = lambda *args, **kwargs: None
                defaults.OMEGA_MY_OWN_SETTING = 'foo'
                om = get_omega_from_apikey('foo', 'bar')
                self.assertIsNotNone(om.defaults.OMEGA_USER_EXTENSIONS)
                self.assertIn('test.backend', om.defaults.OMEGA_STORE_BACKENDS)
                # test that all default values are still there, i.e. config was updated, not replaced
                for real_k, real_v in _real_base_config.OMEGA_STORE_BACKENDS.items():
                    self.assertIn(real_k, om.defaults.OMEGA_STORE_BACKENDS)
                # restore defaults
            defaults = settings(reload=True)
