import unittest

from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression

from omega.store import OmegaStore
import pandas as pd
MONGO_URL = 'mongodb://localhost:27017/omegatest'
MONGO_COLLECTION = 'store'


class StoreTests(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)

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
        store = OmegaStore(mongo_url=MONGO_URL, bucket=MONGO_COLLECTION)
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
        store = OmegaStore(mongo_url=MONGO_URL, bucket=MONGO_COLLECTION,
                           prefix='models/')
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
        store = OmegaStore(mongo_url=MONGO_URL, bucket=MONGO_COLLECTION,
                           prefix='')
        store.put(df, 'mydata')
        df2 = store.get('mydata')
        self.assertTrue(df.equals(df2), "expected dataframes to be equal")
