from unittest import TestCase

from omegaml import Omega
from omegaml.tests.cli.scenarios import CliTestScenarios
from omegaml.tests.util import OmegaTestMixin


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
        self.cli(f'scripts drop helloworld', new_start=True)
        self.assertNotIn('helloworld', self.om.scripts.list())

    def test_cli_scripts_put_pypi(self):
        self.cli(f'scripts list')
        self.assertLogContains('info', '[]')
        pkgpath = 'six'
        self.cli(f'scripts put {pkgpath} six', new_start=True)
        self.assertLogContains('info', 'Metadata')
        self.assertLogContains('info', 'name=six')
        self.cli(f'scripts list')
        self.assertLogSize('info', 1)
        self.assertLogContains('info', 'six')

    def test_cli_scripts_put_git(self):
        self.cli(f'scripts list')
        self.assertLogContains('info', '[]')
        pkgpath = 'git+https://github.com/benjaminp/six.git'
        self.cli(f'scripts put {pkgpath} six', new_start=True)
        self.assertLogContains('info', 'Metadata')
        self.assertLogContains('info', 'name=six')
        self.cli(f'scripts list')
        self.assertLogSize('info', 1)
        self.assertLogContains('info', 'six')

