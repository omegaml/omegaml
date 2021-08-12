import pandas as pd
import unittest
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression

from omegaml import Omega
from omegaml.backends.experiment import ExperimentBackend, OmegaSimpleTracker
from omegaml.documents import Metadata
from omegaml.tests.util import OmegaTestMixin


class TrackingTestCases(OmegaTestMixin, unittest.TestCase):
    def setUp(self):
        self.om = om = Omega()
        self.clean()
        om.models.register_backend(ExperimentBackend.KIND, ExperimentBackend)

    def test_simple_tracking(self):
        # create a model
        om = self.om
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        lr.fit(X, Y)
        # run a local experiment and track its result
        with om.runtime.experiment('myexp') as exp:
            score = lr.score(X, Y)
            exp.log_metric('accuracy', score)
        # check the experiemnt is logged
        self.assertIn('experiments/myexp', om.models.list('experiments/*'))
        exp = om.models.get('experiments/myexp', data_store=om.datasets)
        data = exp.data(event='metric')
        self.assertIsInstance(exp, OmegaSimpleTracker)
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data.iloc[0]['key'], 'accuracy')
        self.assertEqual(data.iloc[0]['value'], score)
        # get back the tracker as an object
        tracker = om.models.get('experiments/myexp', raw=True, data_store=om.datasets)
        self.assertIsInstance(tracker, OmegaSimpleTracker)
        # check remote execution of experiement
        # -- we want to easily transfer code execution to a remote
        # -- while keeping the code semantics as local as possible
        om.models.put(lr, 'mymodel')
        with om.runtime.experiment('myexp', provider='simple') as exp:
            om.runtime.model('mymodel').fit(X, Y)
            om.runtime.model('mymodel').score(X, Y)
            exp.log_metric('accuracy', 1)
            exp.log_artifact(lr, 'mymodel')
            exp.log_artifact(om.models.metadata('mymodel'), 'mymodel_meta')
        tracker = om.models.get('experiments/myexp', raw=True, data_store=om.datasets)
        data = tracker.data()
        self.assertIsInstance(data, pd.DataFrame)
        self.assertEqual(len(data), 13)  # includes runtime task events
        self.assertEqual(len(data[data.event == 'start']), 2)
        self.assertEqual(len(data[data.event == 'stop']), 2)
        self.assertEqual(len(data[data.event == 'artifact']), 2)
        artifacts = data[data.event == 'artifact']['value'].to_list()
        obj = exp.restore_artifact(value=artifacts[0])
        self.assertIsInstance(obj, LogisticRegression)
        obj = exp.restore_artifact(value=artifacts[1])
        self.assertIsInstance(obj, Metadata)

    def test_tracking_from_metadata(self):
        # create a model
        om = self.om
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        lr.fit(X, Y)
        om.models.put(lr, 'mymodel')
        # no tracking
        tracker = om.runtime.experiment('expfoo')
        exp = tracker.experiment
        data = exp.data()
        self.assertIsNone(data)
        # implicit tracking via metadata
        om.models.put(lr, 'mymodel', attributes={
            'experiment': 'expfoo'
        })
        om.runtime.model('mymodel').score(X, Y)
        tracker = om.runtime.experiment('expfoo')
        exp = tracker.experiment
        data = exp.data()
        self.assertIsNotNone(data)
        self.assertEqual(len(data), 4)

    def test_empty_experiment_data(self):
        om = self.om
        with om.runtime.experiment('myexp') as exp:
            pass
        exp = om.models.get('experiments/myexp', data_store=om.datasets)
        self.assertEqual(len(exp.data(event='metric')), 0)
        self.assertEqual(len(exp.data()), 2)  # start and stop events

    def test_experiment_explicit_logging(self):
        om = self.om
        with om.runtime.experiment('myexp') as exp:
            exp.log_metric('accuracy', .98)
        exp = om.models.get('experiments/myexp', data_store=om.datasets)
        self.assertEqual(len(exp.data(event='metric')), 1)

    def test_experiments_not_versioned(self):
        om = self.om
        with om.runtime.experiment('myexp') as exp:
            pass
        meta = om.models.metadata('experiments/myexp')
        self.assertNotIn('versions', meta.attributes)

    def test_experiment_artifact(self):
        om = self.om
        with om.runtime.experiment('myexp') as exp:
            exp.log_artifact(dict(test='data'), 'foo')
        # by name
        data = exp.restore_artifact('foo')
        self.assertIsInstance(data, dict)
        # by value
        data = exp.data(key='foo')
        data = exp.restore_artifact(value=data.iloc[0].value)

    def test_notrack(self):
        # create a model
        om = self.om
        iris = load_iris()
        X = iris.data
        Y = iris.target
        lr = LogisticRegression(solver='liblinear', multi_class='auto')
        lr.fit(X, Y)
        # use runtime to fit model without tracking
        om.models.put(lr, 'mymodel')
        om.runtime.model('mymodel').fit(X, Y)
        tracker = om.runtime.experiment('exp')
        exp = tracker.experiment
        # no tracking, no data
        data = exp.data()
        self.assertIsNone(data)


if __name__ == '__main__':
    unittest.main()
