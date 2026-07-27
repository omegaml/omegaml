from unittest import TestCase

import numpy as np
from numpy.testing import assert_allclose
from sklearn.linear_model import LinearRegression

from omegaml import Omega
from omegaml.backends.virtualobj import virtualobj
from omegaml.mixins.store.objhelper import ObjectHelperMixin
from omegaml.tests.util import OmegaTestMixin


class ObjectHelperTests(OmegaTestMixin, TestCase):
    def setUp(self):
        om = self.om = Omega()
        om.datasets.register_mixin(ObjectHelperMixin)
        om.models.register_mixin(ObjectHelperMixin)
        om.jobs.register_mixin(ObjectHelperMixin)
        self.clean()

    def test_dataset_helper(self):
        """ test using a helper for datasets """
        om = self.om

        @virtualobj
        def myhelper(*args, method=None, universe=None, **kwargs):
            # print("helper", args, kwargs)
            if method == 'get' and universe:
                return 42
            # returning None triggers usual backend handling
            return None

        om.datasets.put(myhelper, 'myhelper', force=True)
        om.datasets.put([0], 'mydata', helper='myhelper')
        # .get() is run through the normal backend
        data = om.datasets.get('mydata')
        self.assertEqual(data, [[0]])
        # trigger custom helper
        # -- note universe=True is specific to our myhelper implementation
        data = om.datasets.get('mydata', universe=True)
        self.assertEqual(data, 42)

    def test_model_helper(self):
        om = self.om

        @virtualobj
        def myhelper(*args, method=None, store=None, meta=None, raw=False, **kwargs):
            # print("helper", args, kwargs)
            if method == 'get' and not raw:
                # simulate loading of the actual model
                class SomeModel:
                    def predict(self, *args):
                        return store.get(meta.name, raw=True)(*args)

                return SomeModel()
            # returning None triggers usual backend handling
            return None

        @virtualobj
        def mymodel(*args, **kwargs):
            # print("model", args, kwargs)
            return 42

        # test helper is called
        om.models.put(myhelper, 'myhelper', replace=True)
        om.models.put(mymodel, 'mymodel', helper='myhelper', replace=True)
        model = om.models.get('mymodel')
        self.assertEqual(model.predict(), 42)
        # test versioning
        om.models.put(mymodel, 'mymodel', helper='myhelper', tag='v1', force=True)
        meta = om.models.put(mymodel, 'mymodel', helper='myhelper', tag='v2', force=True)
        model = om.models.get('mymodel')
        versions = meta.attributes['versions']
        self.assertIn('tags', versions)
        self.assertTrue(all(k in versions['tags'] for k in ('latest', 'v1', 'v2')))
        self.assertEqual(model.predict(), 42)
        # add a version without a helper
        meta = om.models.put(mymodel, 'mymodel', tag='v3', force=True)
        # -- get back the model, now without a helper (helper= was not specified for model version)
        # -- we get back the mymodel function directly
        model = om.models.get('mymodel')
        self.assertTrue(not hasattr(model, 'predict'))
        self.assertEqual(model(), 42)
        # get back a previous version that had a helper
        model = om.models.get('mymodel@v2')
        self.assertEqual(model.predict(), 42)
        # can also get back a helper by specifying get(..., helper='name')
        model = om.models.get('mymodel@v3', helper='myhelper')
        self.assertEqual(model.predict(), 42)

    def test_job_helper(self):
        """ test using a helper for jobs """
        om = self.om

        @virtualobj
        def myhelper(*args, method=None, store=None, meta=None, raw=False, backend=None, **kwargs):
            # print("helper", inspect.getargvalues(inspect.currentframe()))
            from nbformat.v4 import new_code_cell
            from omegaml.util import utcnow
            if method == "get":
                # e.g. add a "created cell"
                nb = backend.get(meta.name)
                cell = new_code_cell(f"created {utcnow()}")
                nb.cells.append(cell)
                return nb

        code = """
        print('hello')
        """

        om.jobs.put(myhelper, 'myhelper', replace=True)
        om.jobs.create(code, 'myjob', helper='myhelper')
        nb = om.jobs.get('myjob')
        self.assertEqual(len(nb.cells), 2)
        self.assertRegex(nb.cells[-1]['source'], r'\d{4}-\d{2}-\d{2}.*')

    def test_supports(self):
        """ test using helper selection by supports= conditions """
        om = self.om

        @virtualobj
        def myhelper(*args, method=None, store=None, meta=None, raw=False, **kwargs):
            if method == 'get':
                return 42

        # selection by kind
        om.datasets.put(myhelper, 'myhelper', supports='python.data', replace=True)
        meta = om.datasets.put({}, 'somedata')
        result = om.datasets.get('somedata')
        self.assertEqual(result, 42)
        # selection by object
        om.models.put(myhelper, 'myhelper', supports='sklearn.linear.*', replace=True)
        reg = LinearRegression()
        om.models.put(reg, 'myreg')
        result = om.models.get('myreg')
        self.assertEqual(result, 42)

    def test_implied_helper(self):
        om = self.om

        @virtualobj
        def mymodel(*args, obj=None, name=None, method=None, data=None, store=None, meta=None, **kwargs):
            class SomeModel:
                def load(self):
                    return store.get(meta.name, raw=True, helper=False)

                def predict(self, *args):
                    actual_model = self.load()
                    return actual_model.predict(*args) + 42

            if method == 'get':
                return SomeModel()
            elif method == 'put':
                store.put(obj, name, helper=False)
            elif method == 'predict':
                return SomeModel().predict(data)
            return None

        # define some model
        lr = LinearRegression()
        X = np.arange(10)
        y = X * 5 + 10
        lr.fit(X.reshape(-1, 1), y)
        # store model with an implied helper
        meta = om.models.put((lr, mymodel), 'mymodel', replace=True)
        self.assertEqual(meta.kind, 'sklearn.joblib')
        self.assertEqual(meta.kind_meta['helper'], ".helpers/mymodel")
        # explicit get returns SomeModel
        model = om.models.get('mymodel')
        self.assertTrue('SomeModel' in str(model))
        assert_allclose(model.predict([[1]]), np.array([1. * 5 + 10 + 42]))
        # implicit predict returns just the result
        model = om.runtime.model('mymodel')
        result = model.predict([[1]])
        assert_allclose(result.get(), np.array([1. * 5 + 10 + 42]))
