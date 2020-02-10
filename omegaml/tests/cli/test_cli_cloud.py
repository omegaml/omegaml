from unittest import TestCase, skip

from omegaml import Omega
from omegaml.tests.cli.scenarios import CliTestScenarios
from omegaml.tests.util import OmegaTestMixin


class CliModelsTest(CliTestScenarios, OmegaTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.om = Omega()
        self.clean()

    @skip("only works in enterprise context")
    def test_cli_cloud_add_resource(self):
        self.cli('--config ../../../config.yml cloud add worker')
