from unittest import TestCase

from dashserve.jupyter import DashserveApp
from dashserve.tests import myapp
from omegaml.backends.dashapp import DashAppBackend
from omegaml.store import OmegaStore


class DashAppBackendTests(TestCase):
    def setUp(self):
        self.app = myapp.app
        self.store = OmegaStore(prefix='scripts/')
        self.backend = DashAppBackend(model_store=self.store, data_store=self.store)
        [self.store.drop(name) for name in self.store.list()]

    def tearDown(self):
        pass

    def test_supports(self):
        """ test DashAppBackend supports a jupyter dash app """
        self.assertTrue(DashAppBackend.supports(self.app, 'myapp'))

    def test_put_get_dashapp(self):
        """ test a jupyter dash app can be stored and restored"""
        app = self.app
        self.backend.put(self.app, 'myapp')
        self.assertIn('myapp', self.store.list())
        restored_app = self.backend.get('myapp')
        self.assertIsInstance(restored_app, DashserveApp)
        self.assertEqual(restored_app.config.external_stylesheets , app.config.external_stylesheets)



