from unittest import TestCase

import unittest
from flask import url_for

from omegaml.server.app import create_app
from omegaml.tests.util import OmegaTestMixin


class TrackingViewTests(OmegaTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()
        globals().update(url_for=self.url_for)

    def url_for(self, endpoint, **kwargs):
        from flask import url_for
        with self.app.test_request_context():
            return url_for(endpoint, **kwargs)

    def test_experiment_data(self):
        om = self.om
        exp = om.runtime.experiment('foo')
        for i in range(1, 10):
            with exp:
                exp.log_metric('accuracy', 0.8)
        resp = self.client.get(url_for('omega-server.tracking_api_experiment_data',
                                       name='foo'))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(url_for('omega-server.tracking_api_experiment_data',
                                       name='foo', start=3, nrows=5))
        self.assertEqual(resp.status_code, 200)
        data = resp.json
        self.assertEqual(len(data['data']), 5)
        resp = self.client.get(url_for('omega-server.tracking_api_experiment_data',
                                       name='foo', since='-1d', end='now'))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(url_for('omega-server.tracking_api_experiment_data',
                                       name='foo', start=100, nrows=10))
        self.assertEqual(resp.status_code, 200)
        data = resp.json
        self.assertEqual(len(data['data']), 0)
        resp = self.client.get(url_for('omega-server.tracking_api_experiment_data',
                                       name='foo', since='-10d', end='now', start=100, nrows=10))
        self.assertEqual(resp.status_code, 200)
        data = resp.json
        self.assertEqual(len(data['data']), 0)

    def test_plot_metrics(self):
        om = self.om
        exp = om.runtime.experiment('foo')
        for i in range(1, 10):
            with exp:
                exp.log_metric('accuracy', 0.8)
        resp = self.client.get(url_for('omega-server.tracking_api_plot_metrics',
                                       name='foo') + '?runs=')
        self.assertEqual(resp.status_code, 200)


if __name__ == '__main__':
    unittest.main()
