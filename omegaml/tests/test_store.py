import StringIO
import unittest
from zipfile import ZipFile

from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression

from omegaml.store import OmegaStore
from omegaml.util import override_settings, delete_database
import pandas as pd
override_settings(
    OMEGA_MONGO_URL='mongodb://localhost:27017/omegatest',
    OMEGA_MONGO_COLLECTION='store'
)


class StoreTests(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)
        delete_database()

    def tearDown(self):
        unittest.TestCase.tearDown(self)

    def test_package_model(self):
        # create a test model
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression()
        lr.fit(X, Y)
        result = lr.predict(X)
        # package locally
        store = OmegaStore()
        zipfname = store._package_model(lr, 'models/foo')
        # load it, try predicting
        lr2 = store._extract_model(zipfname)
        self.assertIsInstance(lr2, LogisticRegression)
        result2 = lr2.predict(X)
        self.assertTrue((result == result2).all())

    def test_put_model(self):
        # create a test model
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression()
        lr.fit(X, Y)
        result = lr.predict(X)
        # store it remote
        store = OmegaStore()
        store.put(lr, 'models/foo')
        # get it back, try predicting
        lr2 = store.get('models/foo')
        self.assertIsInstance(lr2, LogisticRegression)
        result2 = lr2.predict(X)
        self.assertTrue((result == result2).all())

    def test_put_model_with_prefix(self):
        # create a test model
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression()
        lr.fit(X, Y)
        result = lr.predict(X)
        # store it remote
        store = OmegaStore(prefix='models/')
        store.put(lr, 'foo')
        # get it back, try predicting
        lr2 = store.get('foo')
        self.assertIsInstance(lr2, LogisticRegression)
        result2 = lr2.predict(X)
        self.assertTrue((result == result2).all())

    def test_put_dataframe(self):
        # create some dataframe
        df = pd.DataFrame({
            'a': range(1, 10),
            'b': range(1, 10)
        })
        store = OmegaStore(prefix='')
        store.put(df, 'mydata')
        df2 = store.get('mydata')
        self.assertTrue(df.equals(df2), "expected dataframes to be equal")

    def test_put_python_dict(self):
        # create some data
        data = {
            'a': range(1, 10),
            'b': range(1, 10)
        }
        store = OmegaStore(prefix='')
        store.put(data, 'mydata')
        data2 = store.get('mydata')
        self.assertEquals([data], data2)

    def test_get_forced_python(self):
        """
        this tests we can retrieve data as python values

        the purpose is to test the basic mode of OmegaStore in 
        case pandas and scikit learn are not available 
        """
        store = OmegaStore(prefix='')
        # pure data
        data = {
            'a': range(1, 10),
            'b': range(1, 10)
        }
        meta = store.put(data, 'data')
        data2 = store.get('data', force_python=True)[0]
        self.assertEqual(data, data2)
        # dataframe
        # create some dataframe
        df = pd.DataFrame({
            'a': range(1, 10),
            'b': range(1, 10)
        })
        store.put(df, 'mydata')
        df2 = store.get('mydata', force_python=True)
        for r in df2:
            del r['_id']
        df2 = pd.DataFrame(df2)
        self.assertTrue(df.equals(df2), "expected dataframes to be equal")
        # model
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression()
        lr.fit(X, Y)
        # store it remote
        store.put(lr, 'foo')
        # get it back as a zipfile
        lr2 = store.get('foo', force_python=True)
        with ZipFile(StringIO.StringIO(lr2)) as zipf:
            self.assertIn('foo', zipf.namelist())
