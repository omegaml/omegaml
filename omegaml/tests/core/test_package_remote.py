from unittest import TestCase

from shutil import rmtree

from omegaml import Omega
from omegaml.backends.package import PythonPipSourcedPackageData
from omegaml.util import settings, delete_database, mkdirs


class PythonRemotePackageDataTests(TestCase):
    _multiprocess_can_split_ = False

    def setUp(self):
        self.defaults = settings()
        OMEGA_STORE_BACKENDS = self.defaults.OMEGA_STORE_BACKENDS
        self.backend = backend = 'omegaml.backends.package.PythonPipSourcedPackageData'
        if PythonPipSourcedPackageData.KIND not in OMEGA_STORE_BACKENDS:
            OMEGA_STORE_BACKENDS[PythonPipSourcedPackageData.KIND] = backend
        self.om = Omega()
        delete_database()
        self.pkgsdir = self.om.scripts.get_backend_bykind(PythonPipSourcedPackageData.KIND).packages_path
        mkdirs(self.pkgsdir)

    def tearDown(self):
        rmtree(self.pkgsdir, ignore_errors=True)

    def test_put_pypi(self):
        om = self.om
        pkgsrc = 'pypi://six'
        om.scripts.put(pkgsrc, 'six')
        metas = om.scripts.list(raw=True)
        self.assertEqual(metas[0].kind, 'pipsrc.package')

    def test_get_pypi(self):
        om = self.om
        pkgsrc = 'pypi://six'
        om.scripts.put(pkgsrc, 'six')
        mod1 = om.scripts.get('six')
        self.assertIsNotNone(mod1)
        self.assertIn('six', mod1.__file__)

    def test_get_pypi_versioned(self):
        om = self.om
        pkgsrc = 'pypi://six==1.15.0'
        om.scripts.put(pkgsrc, 'six')
        mod1 = om.scripts.get('six')
        self.assertIsNotNone(mod1)
        self.assertIn('six', mod1.__file__)

    def test_get_git(self):
        om = self.om
        pkgsrc = 'git+https://github.com/benjaminp/six.git'
        om.scripts.put(pkgsrc, 'six')
        mod1 = om.scripts.get('six')
        self.assertIsNotNone(mod1)
        self.assertIn('six', mod1.__file__)

    def test_get_git_versioned(self):
        om = self.om
        pkgsrc = 'git+https://github.com/benjaminp/six.git@1.15.0'
        om.scripts.put(pkgsrc, 'six')
        mod1 = om.scripts.get('six')
        self.assertIsNotNone(mod1)
        self.assertIn('six', mod1.__file__)
