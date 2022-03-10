import json

import datetime
import os
import sys
from shutil import rmtree
from unittest import TestCase

from omegaml import Omega
from omegaml.backends.package import PythonPackageData
from omegaml.backends.package.packager import build_sdist
from omegaml.util import settings, delete_database, mkdirs


class PythonLocalPackageDataTests(TestCase):
    _multiprocess_can_split_ = False

    def setUp(self):
        self.basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        self.defaults = settings()
        OMEGA_STORE_BACKENDS = self.defaults.OMEGA_STORE_BACKENDS
        OMEGA_STORE_MIXINS = self.defaults.OMEGA_STORE_MIXINS
        self.backend = backend = 'omegaml.backends.package.PythonPackageData'
        self.mixin = mixin = 'omegaml.mixins.store.package.PythonPackageMixin'
        if PythonPackageData.KIND not in OMEGA_STORE_BACKENDS:
            OMEGA_STORE_BACKENDS[PythonPackageData.KIND] = backend
        if mixin not in OMEGA_STORE_MIXINS:
            OMEGA_STORE_MIXINS.append(mixin)
        self.om = Omega()
        delete_database()
        self.pkgsdir = self.om.scripts.get_backend_bykind(PythonPackageData.KIND).packages_path
        self.distdir = os.path.join(self.basepath,  'demo', 'helloworld', 'dist')
        rmtree(self.distdir, ignore_errors=True)
        mkdirs(self.distdir)
        mkdirs(self.pkgsdir)

    def tearDown(self):
        rmtree(self.pkgsdir, ignore_errors=True)
        rmtree(self.distdir)

    def test_build_sdist(self):
        pkgpath = os.path.abspath(os.path.join(self.basepath, 'demo', 'helloworld'))
        distdir = os.path.join(pkgpath, 'dist')
        sdist = build_sdist(pkgpath, self.distdir)
        version = sdist.metadata.version
        pkgname = sdist.metadata.name
        pkgdist = os.path.join(distdir, '{pkgname}-{version}.tar.gz'.format(**locals()))
        self.assertTrue(os.path.exists(pkgdist))

    def test_build_put(self):
        om = self.om
        pkgpath = os.path.abspath(os.path.join(self.basepath, 'demo', 'helloworld'))
        pkgsrc = 'pkg://{}'.format(pkgpath)
        om.scripts.put(pkgsrc, 'helloworld')
        metas = om.scripts.list(raw=True)
        self.assertEqual(metas[0].kind, 'python.package')

    def test_build_get(self):
        om = self.om
        pkgpath = os.path.abspath(os.path.join(self.basepath, 'demo', 'helloworld'))
        pkgsrc = 'pkg://{}'.format(pkgpath)
        om.scripts.put(pkgsrc, 'helloworld')
        # load and install
        # -- since this is loading from gridfs first and installing the package using pip
        #    this will be orders of magnitues slower than just getting the package when
        #    already installed the second time around (see second step & test)
        dtstart = datetime.datetime.now()
        mod1 = om.scripts.get('helloworld')
        dtend = datetime.datetime.now()
        loadtime1 = dtend - dtstart
        # see if we can just get from the existing local installation
        # -- this will just load the module from disk
        dtstart = datetime.datetime.now()
        mod2 = om.scripts.get('helloworld')
        dtend = datetime.datetime.now()
        loadtime2 = dtend - dtstart
        # assert that loading from the local module from disk is faster than loading from gridfs
        self.assertLess(loadtime2, loadtime1)
        self.assertEqual(mod1.__file__, mod2.__file__)

    def test_install(self):
        om = self.om
        pkgpath = os.path.abspath(os.path.join(self.basepath, 'demo', 'helloworld'))
        pkgsrc = 'pkg://{}'.format(pkgpath)
        om.scripts.put(pkgsrc, 'helloworld')
        om.scripts.install()
        self.assertIn('helloworld', sys.modules)

    def test_install_fully_qualified(self):
        om = self.om
        pkgpath = os.path.abspath(os.path.join(self.basepath, 'demo', 'helloworld', 'setup.py'))
        pkgsrc = 'pkg://{}'.format(pkgpath)
        om.scripts.put(pkgsrc, 'helloworld')
        om.scripts.install()
        self.assertIn('helloworld', sys.modules)

    def test_install_specifics(self):
        om = self.om
        pkgpath = os.path.abspath(os.path.join(self.basepath, 'demo', 'helloworld'))
        pkgsrc = 'pkg://{}'.format(pkgpath)
        om.scripts.put(pkgsrc, 'helloworld')
        om.scripts.install('helloworld')
        self.assertIn('helloworld', sys.modules)
        del sys.modules['helloworld']
        om.scripts.install(['helloworld'])
        self.assertIn('helloworld', sys.modules)

    def test_runtime(self):
        om = self.om
        pkgpath = os.path.abspath(os.path.join(self.basepath, 'demo', 'helloworld'))
        pkgsrc = 'pkg://{}'.format(pkgpath)
        om.scripts.put(pkgsrc, 'helloworld')
        print("***omega test_runtime (om, om.runtime)", om, om.runtime)
        result = om.runtime.script('helloworld').run(text='foo')
        data = json.loads(result.get())
        self.assertIn('runtimes', data)
        expected = ['hello from helloworld', {'text': 'foo', 'pure_python': False}]
        self.assertEqual(data['result'], expected)

    def test_sysargv_stability(self):
        """
        test scripts.put does not change sys.argv
        """
        om = self.om
        orig_sysargv = ' '.join(sys.argv)
        pkgpath = os.path.abspath(os.path.join(self.basepath, 'demo', 'helloworld'))
        pkgsrc = 'pkg://{}'.format(pkgpath)
        om.scripts.put(pkgsrc, 'helloworld')
        new_sysargv = ' '.join(sys.argv)
        self.assertEqual(new_sysargv, orig_sysargv)


