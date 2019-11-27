from unittest import TestCase

from omegaml import Omega
from omegaml.tests.cli.scenarios import CliTestScenarios
from omegaml.tests.util import OmegaTestMixin


class CliModelsTest(CliTestScenarios, OmegaTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.om = Omega()
        self.clean()

    def test_cli_models_list(self):
        # start with an empty list
        self.cli('models list')
        expected = self.pretend_log([])
        self.assertLogSize('info', 1)
        self.assertLogEqual('info', expected)
        # create a model
        self.make_model('reg')
        self.cli('models list')
        expected = self.pretend_log(['reg'], start_empty=True)
        self.assertLogSize('info', 1)
        self.assertLogEqual('info', expected)
        # check we can get back a Metadata object
        self.cli('models list --raw')
        expected = self.pretend_log('Metadata(')
        self.assertLogContains('info', expected)

    def test_cli_models_put(self):
        self.cli(f'models put omegaml.example.demo.modelfn.create_model testmodel')
        expected = self.pretend_log('Metadata(name=testmodel')
        self.assertLogContains('info', expected)

    def test_cli_models_metadata(self):
        self.make_model('reg')
        self.cli('models metadata reg')
        expected = self.pretend_log('"kind": "sklearn.joblib"')
        self.assertLogContains('info', expected)
        expected = self.pretend_log('"name": "reg"')
        self.assertLogContains('info', expected)



