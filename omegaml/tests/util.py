from http import HTTPStatus

import os
import warnings

from omegaml import Omega
from omegaml.client.lunamon import LunaMonitor


class OmegaTestMixin(object):
    def setUp(self):
        super().setUp()
        self.om = Omega()
        self.clean()

    def tearDown(self):
        super().tearDown()
        LunaMonitor.stop_all()

    def shortDescription(self):
        # always print method name instead of docstring
        # see unittest.TestCase for details
        return None

    def clean(self, bucket=None):
        # stop monitoring to avoid interference with tests
        LunaMonitor.stop_all()
        # clean om stores
        om = self.om[bucket] if bucket is not None else self.om
        for element in ('models', 'jobs', 'datasets', 'scripts', 'streams'):
            part = getattr(om, element)
            drop = part.drop
            drop_kwargs = {}
            if element == 'streams':
                drop_kwargs = {'keep_data': False}
            # drop all members
            [drop(m.name,
                  force=True,
                  **drop_kwargs) for m in part.list(hidden=True, include_temp=True, raw=True)]
            # ignore system members, as they may get recreated e.g. by LunaMonitor
            existing = [m.name for m in part.list(hidden=True, include_temp=True, raw=True)
                        if not m.name.startswith('.system')]
            self.assertListEqual(existing, [])

    @property
    def _async_headers(self):
        return {
            'async': 'true'
        }

    def _check_async(self, resp):
        # check resp is async, then retrieve actual result as type TaskOutput
        self.assertEqual(resp.status_code, 202)
        data = resp.get_json()
        location = resp.headers['Location']
        self.assertRegex(location, r'.*/api/v1/task/.*/result')
        # check we can get back the actual result
        resp = self.client.get(location.replace('http://localhost', ''), json={
            'resource_uri': data.get('resource_uri')
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'SUCCESS')
        self.assertIn(data['task_id'], location)
        return resp

    def assertHttpOK(self, resp):
        self.assertEqual(resp.status_code, HTTPStatus.OK)

    def deserialize(self, resp):
        return resp.get_json()


def tf_in_eager_execution():
    # condition for unittest.skipIf decorator
    import tensorflow as tf
    return tf.executing_eagerly()


def tf_perhaps_eager_execution(*args, **kwargs):
    """
    test support to enable tf eager execution

    conditionally set eager execution if TF_EAGER env
    variable is yet to 1. else the eager state is not
    changed.
    """
    tf_eager_switch = os.environ.get('TF_EAGER', False)
    if int(tf_eager_switch):
        import tensorflow as tf
        try:
            tf.enable_eager_execution(*args, **kwargs)
            warnings.warn('TensorFlow eager execution enabled')
        except ValueError as e:
            warnings.warn(str(e))
    else:
        warnings.warn('TensorFlow eager execution not enabled TF_EAGER={tf_eager_switch}'.format(**locals()))


def clear_om(om):
    for bucket in om.buckets:
        omx = om[bucket]
        for omstore in (omx.datasets, omx.jobs, omx.models, omx.scripts, omx.streams):
            [omstore.drop(name, force=True) for name in omstore.list(include_temp=True, hidden=True)]


import math


def almost_equal(a, b, tolerance=1e-9):
    """Check if two floating-point numbers are almost equal within a given tolerance."""
    return math.isclose(a, b, abs_tol=tolerance)


def dict_almost_equal(dict1, dict2, tolerance=1e-9):
    """Recursively check if two nested dictionaries are almost equal."""
    if dict1.keys() != dict2.keys():
        return False
    for key in dict1:
        val1 = dict1[key]
        val2 = dict2[key]
        if isinstance(val1, dict) and isinstance(val2, dict):
            if not dict_almost_equal(val1, val2, tolerance):
                return False
        elif isinstance(val1, float) and isinstance(val2, float):
            if not almost_equal(val1, val2, tolerance):
                raise AssertionError(f"Values key {key}: {val1} and {val2} are not almost equal")
        else:
            if val1 != val2:
                raise AssertionError(f"Values key {key}: {val1} and {val2} are not equal")
    return True
