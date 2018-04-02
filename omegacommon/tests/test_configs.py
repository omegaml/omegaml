from io import StringIO
from unittest import TestCase
from unittest.mock import patch, MagicMock

import omegaml
from omegacommon.userconf import get_omega_from_apikey
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
        cfgfile = StringIO(data)
        cfgfile.seek(0)
        update_from_config(self.defaults, cfgfile)
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

    def test_update_from_dict(self):
        data = {
            'OMEGA_MONGO_URL': 'updated-foo'
        }
        update_from_dict(data, self.defaults)
        self.assertIn('OMEGA_MONGO_URL', self.defaults)
        self.assertEqual(self.defaults['OMEGA_MONGO_URL'], 'updated-foo')
        self.assertNotIn('NOTOMEGA_VALUE', self.defaults)

    @patch('omegaml.defaults.OMEGA_MONGO_URL')
    def test_config_from_apikey(self, orig):
        """
        Test an Omega instance can be created from user specific configs
        """
        from omegaml import defaults
        defaults.OMEGA_MONGO_URL = 'foo'
        # we patch the actual api call to avoid having to set up the user db
        # the objective here is to test get_omega_from_apikey
        with patch('omegacommon.userconf.get_user_config_from_api') as mock:
            mock.return_value = {
                'objects': [
                    {
                        'data': {
                            'OMEGA_MONGO_URL': 'updated-foo'
                        }
                    }
                ]
            }
            get_omega_from_apikey.data = {}
            om = get_omega_from_apikey('foo', 'bar')
            self.assertEqual(om.datasets.mongo_url, 'updated-foo')

