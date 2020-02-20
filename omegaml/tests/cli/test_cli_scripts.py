from unittest import TestCase

import os

import nbformat

from omegaml import Omega
from omegaml.tests.cli.scenarios import CliTestScenarios
from omegaml.tests.util import OmegaTestMixin
from omegaml.util import temp_filename


class CliScriptsTest(CliTestScenarios, OmegaTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.om = Omega()
        self.clean()

    def test_cli_scripts_list_put(self):
        self.cli(f'scripts list')
        self.assertLogContains('info', '[]')
        pkgpath = self.get_package_path()
        self.cli(f'scripts put {pkgpath} helloworld', new_start=True)
        self.assertLogContains('info', 'Metadata')
        self.assertLogContains('info', 'name=helloworld')
        self.cli(f'scripts list')
        self.assertLogSize('info', 1)
        self.assertLogContains('info', 'helloworld')

    def test_cli_scripts_drop(self):
        pkgpath = self.get_package_path()
        self.cli(f'scripts put {pkgpath} helloworld', new_start=True)
        self.assertIn('helloworld', self.om.scripts.list())
        self.cli(f'scripts delete helloworld', new_start=True)
        self.assertNotIn('helloworld', self.om.scripts.list())

