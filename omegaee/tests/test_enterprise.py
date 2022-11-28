from unittest import mock
from unittest.mock import MagicMock

import requests
from celery.apps.worker import Worker
from django.test import TestCase

from omegaee.pingserver import CeleryWorkerPingServer


class OmegaEnterpriseTests(TestCase):
    def test_omegaee_imports(self):
        """
        test omegaml module setup uses enterprise implementation
        """
        # avoid circular imports
        import omegaml as om
        from omegaee.omega import EnterpriseOmegaDeferredInstance
        from omegaee.omega import EnterpriseOmega
        self.assertIsInstance(om._omega._om, EnterpriseOmegaDeferredInstance)
        self.assertTrue(om.Omega is EnterpriseOmega)

    def test_runtime_health_ping(self):
        # mock Celery as instantiating for real interferes with other tests
        # -- we want to test CeleryWorkerPingServer, not Celery
        worker = MagicMock()
        worker.app = MagicMock()
        worker.hostname='celery@localhost'
        server = CeleryWorkerPingServer(worker, port=8199)
        with mock.patch.object(server.app, 'control') as control:
            inspect = MagicMock()
            inspect.ping.return_value = {'celery@localhost': {'ok': 'pong'}}
            control.inspect.return_value = inspect
            server.start()
            try:
                resp = requests.get('http://localhost:8199')
                self.assertEqual(resp.status_code, 200)
            finally:
                server.stop()



