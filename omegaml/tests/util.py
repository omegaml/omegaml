import os
import warnings
from http import HTTPStatus


class OmegaTestMixin(object):
    def clean(self, bucket=None):
        om = self.om[bucket] if bucket is not None else self.om
        for element in ('models', 'jobs', 'datasets', 'scripts', 'streams'):
            part = getattr(om, element)
            drop = part.drop
            [drop(m.name, force=True) for m in part.list(hidden=True, include_temp=True, raw=True)]
            self.assertListEqual(part.list(hidden=True, include_temp=True), [])

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
        self.assertRegexpMatches(location, r'http://localhost/api/v1/task/.*/result')
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
    for omstore in (om.datasets, om.jobs, om.models):
        [omstore.drop(name) for name in omstore.list()]
