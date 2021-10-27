import json
import os
import unittest
from pathlib import Path

from omegaml import Omega
from omegaml.backends.rsystem.rscripts import RPackageData, RScript
from omegaml.tests.util import OmegaTestMixin


class RSystemScriptTests(OmegaTestMixin, unittest.TestCase):
    """ test running R functionality from within Python
    """

    def setUp(self):
        om = self.om = Omega()
        om.scripts.register_backend(RPackageData.KIND, RPackageData)
        self.clean()
        # force test mode for omega run from R
        os.environ['OMEGA_TEST_MODE'] = "yes"

    def _write_helloR(self):
        import omegaml

        om = self.om
        package_path = (Path(omegaml.__file__).parent / 'example' /
                        'demo' / 'helloR')
        meta = om.scripts.put(f'R://{package_path}/app.R', 'helloR')
        return meta

    def test_rpackage(self):
        """ test we can store and retrieve R packages """
        om = self.om
        meta = self._write_helloR()
        mod = om.scripts.get('helloR')
        self.assertIsInstance(mod, RScript)
        self.assertTrue(Path(mod.appdir).exists())
        self.assertTrue((Path(mod.appdir) / 'app.R').exists())
        output = mod.run(self.om, foo='bar')
        self.assertIsInstance(output, dict)
        self.assertIn('message', output)
        self.assertEqual(output['message'], ['hello from R'])
        self.assertEqual(output['scripts'], ['helloR'])

    def test_rpackage_runtime(self):
        """ test we can run R packages on the runtime """
        om = self.om
        meta = self._write_helloR()
        result = om.runtime.script('helloR').run().get()
        result = json.loads(result)
        self.assertIn('result', result)
        output = result['result']
        self.assertIn('message', output)
        self.assertEqual(output['message'], ['hello from R'])
        self.assertEqual(output['scripts'], ['helloR'])

