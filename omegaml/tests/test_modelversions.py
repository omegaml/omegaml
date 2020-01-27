from unittest import TestCase

import numpy as np
from sklearn.linear_model import LinearRegression

from omegaml import Omega
from omegaml.mixins.store.modelversion import ModelVersionMixin
from omegaml.tests.util import OmegaTestMixin


class ModelVersionMixinTests(OmegaTestMixin, TestCase):
    def setUp(self):
        self.om = Omega()
        self.clean()

    def test_version_on_put(self):
        store = self.om.models
        store.register_mixin(ModelVersionMixin)
        clf = LinearRegression()
        meta = store.put(clf, 'regmodel')
        self.assertIn('versions', meta.attributes)
        models = store.list(include_temp=True)
        latest = meta.attributes['versions']['tags']['latest']
        store_key = store._model_version_store_key('regmodel', latest)
        self.assertIn(store_key, models)

    def test_get_version_by_index(self):
        store = self.om.models
        store.register_mixin(ModelVersionMixin)
        clf = LinearRegression()
        clf.version_ = 1
        meta = store.put(clf, 'regmodel')
        clf.version_ = 2
        meta = store.put(clf, 'regmodel')
        clf_ = store.get('regmodel', version=-1)
        self.assertEqual(clf_.version_, 2)
        clf_ = store.get('regmodel', version=-2)
        self.assertEqual(clf_.version_, 1)
        clf_ = store.get('regmodel')
        self.assertEqual(clf_.version_, 2)

    def test_get_version_by_tag(self):
        store = self.om.models
        store.register_mixin(ModelVersionMixin)
        clf = LinearRegression()
        clf.version_ = 1
        meta = store.put(clf, 'regmodel', tag='version1')
        clf.version_ = 2
        meta = store.put(clf, 'regmodel', tag='version2')
        clf_ = store.get('regmodel', tag='version2')
        self.assertEqual(clf_.version_, 2)
        clf_ = store.get('regmodel', tag='version1')
        self.assertEqual(clf_.version_, 1)
        clf_ = store.get('regmodel')
        self.assertEqual(clf_.version_, 2)

    def test_get_version_by_attag(self):
        store = self.om.models
        store.register_mixin(ModelVersionMixin)
        clf = LinearRegression()
        clf.version_ = 1
        meta = store.put(clf, 'regmodel', tag='version1')
        clf.version_ = 2
        meta = store.put(clf, 'regmodel', tag='version2')
        clf_ = store.get('regmodel@version2')
        self.assertEqual(clf_.version_, 2)
        clf_ = store.get('regmodel@version1')
        self.assertEqual(clf_.version_, 1)
        clf_ = store.get('regmodel')
        self.assertEqual(clf_.version_, 2)

    def test_get_version_by_commit(self):
        store = self.om.models
        store.register_mixin(ModelVersionMixin)
        clf = LinearRegression()
        clf.version_ = 1
        meta = store.put(clf, 'regmodel')
        clf.version_ = 2
        meta = store.put(clf, 'regmodel')
        meta = store.metadata('regmodel')
        commit1 = meta.attributes['versions']['commits'][-2]['ref']
        commit2 = meta.attributes['versions']['commits'][-1]['ref']
        clf_ = store.get('regmodel', commit=commit2)
        self.assertEqual(clf_.version_, 2)
        clf_ = store.get('regmodel', commit=commit1)
        self.assertEqual(clf_.version_, 1)
        clf_ = store.get('regmodel')
        self.assertEqual(clf_.version_, 2)

    def test_get_metadata_by_version(self):
        store = self.om.models
        store.register_mixin(ModelVersionMixin)
        clf = LinearRegression()
        clf.version_ = 1
        meta1 = store.put(clf, 'regmodel', tag='commit1')
        clf.version_ = 2
        meta2 = store.put(clf, 'regmodel', tag='commit2')
        self.assertEqual(meta1.id, meta2.id)
        meta_commit1_byname = store.metadata(meta2.attributes['versions']['commits'][-2]['name'])
        meta_commit2_byname = store.metadata(meta2.attributes['versions']['commits'][-1]['name'])
        meta_commit1_bymeta = store.metadata('regmodel@commit1', raw=True)
        meta_commit2_bymeta = store.metadata('regmodel@commit2', raw=True)
        self.assertEqual(meta_commit1_bymeta.id, meta_commit1_byname.id)
        self.assertEqual(meta_commit2_bymeta.id, meta_commit2_byname.id)

    def test_via_runtime(self):
        store = self.om.models
        store.register_mixin(ModelVersionMixin)
        reg = LinearRegression()
        reg.coef_ = np.array([2])
        reg.intercept_ = 10
        store.put(reg, 'regmodel', tag='commit1')
        reg.coef_ = np.array([5])
        reg.intercept_ = 0
        store.put(reg, 'regmodel', tag='commit2')
        # via past version pointer
        r1 = self.om.runtime.model('regmodel^').predict([10]).get()
        r2 = self.om.runtime.model('regmodel').predict([10]).get()
        self.assertEqual(r1[0], 10 * 2 + 10)
        self.assertEqual(r2[0], 10 * 5 + 0)
        # via version tag
        r1 = self.om.runtime.model('regmodel@commit1').predict([10]).get()
        r2 = self.om.runtime.model('regmodel@commit2').predict([10]).get()
        self.assertEqual(r1[0], 10 * 2 + 10)
        self.assertEqual(r2[0], 10 * 5 + 0)

    def test_nonexistent(self):
        store = self.om.models
        store.register_mixin(ModelVersionMixin)
        store.metadata('nonexistent')
        store.get('nonexistent')

    def test_dropversion(self):
        store = self.om.models
        store.register_mixin(ModelVersionMixin)
        reg = LinearRegression()
        reg.coef_ = np.array([2])
        reg.intercept_ = 10
        store.put(reg, 'regmodel', tag='commit1')
        reg.coef_ = np.array([5])
        reg.intercept_ = 0
        store.put(reg, 'regmodel', tag='commit2')




