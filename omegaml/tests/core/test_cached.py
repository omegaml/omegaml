from unittest import TestCase

from omegaml.mixins.store.cached import CachedObjectMixin


class CachedMixinTests(TestCase):
    def setUp(self):
        from omegaml import Omega
        self.om = Omega()
        self.om.datasets.register_mixin(CachedObjectMixin)
        self.om.datasets.drop('test_cached', force=True)

    def tearDown(self):
        self.om.datasets.drop('test_cached', force=True)

    def test_nocache(self):
        data = {'foo': 'bar'}
        self.om.datasets.put(data, 'test_cached')
        obj = self.om.datasets.get('test_cached')
        self.assertNotIn('test_cached', self.om.datasets._object_cache)
        obj_ = self.om.datasets.get('test_cached')
        self.assertNotEqual(id(obj), id(obj_), 'should not be cached')

    def test_cache_byname(self):
        data = {'foo': 'bar'}
        self.om.datasets.put(data, 'cached/test_cached')
        obj = self.om.datasets.get('cached/test_cached')
        self.assertIn('cached/test_cached', self.om.datasets._object_cache)
        obj_ = self.om.datasets.get('cached/test_cached')
        self.assertEqual(id(obj), id(obj_))
        # update obj, we should get back a new object
        data = {'fox': 'bax'}
        self.om.datasets.put(data, 'cached/test_cached')
        obj_ = self.om.datasets.get('cached/test_cached')
        # check cache works for newly cached object
        self.assertNotEqual(id(obj), id(obj_))
        obj = self.om.datasets.get('cached/test_cached')
        self.assertEqual(id(obj), id(obj_))

    def test_cache_bymeta(self):
        data = {'foo': 'bar'}
        self.om.datasets.put(data, 'test_cached', attributes={'cached': True})
        obj = self.om.datasets.get('test_cached')
        self.assertIn('test_cached', self.om.datasets._object_cache)
        obj_ = self.om.datasets.get('test_cached')
        self.assertEqual(id(obj), id(obj_))
        # update obj, we should get back a new object
        data = {'fox': 'bax'}
        self.om.datasets.put(data, 'test_cached', attributes={'cached': True})
        obj_ = self.om.datasets.get('test_cached')
        # check cache works for newly cached object
        self.assertNotEqual(id(obj), id(obj_))
        obj = self.om.datasets.get('test_cached')
        self.assertEqual(id(obj), id(obj_))

