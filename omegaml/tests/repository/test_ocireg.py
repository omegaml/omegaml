from unittest import TestCase

import unittest

from omegaml import Omega
from omegaml.backends.repository.ocireg import OCIRegistryBackend
from omegaml.backends.repository.orasreg import OrasOciRegistry
from omegaml.tests.util import OmegaTestMixin


class TestOCIRegistryBackend(OmegaTestMixin, TestCase):
    """ """

    def setUp(self):
        self.om = om = Omega()
        om.models.register_backend(OCIRegistryBackend.KIND, OCIRegistryBackend)
        self.clean()

    def test_putget_namespaced(self):
        om = self.om
        # -- without image
        om.models.put('oci://ghcr.io/miraculixx', 'ocireg')
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.url, 'ghcr.io')
        self.assertEqual(reg.repo, None)
        # -- specify image on load
        reg = om.models.get('ocireg', image='myimage:latest')
        self.assertEqual(reg.repo, 'miraculixx/myimage:latest')
        # -- with image
        om.models.put('oci://ghcr.io/miraculixx/myimage', 'ocireg')
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.repo, 'miraculixx/myimage:latest')

    def test_putget_bare(self):
        om = self.om
        # -- registry with no image specified
        om.models.put('oci://ghcr.io', 'ocireg')
        reg = om.models.get('ocireg')
        self.assertEqual(reg.repo, None)
        # -- requires specification of image on .get()
        reg = om.models.get('ocireg', image='namespace/myimage')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.repo, 'namespace/myimage:latest')
        # -- registry with namespace, but no image
        om.models.put('oci://ghcr.io/namespace', 'ocireg')
        reg = om.models.get('ocireg', image='myimage:latest')
        self.assertEqual(reg.repo, 'namespace/myimage:latest')

    def test_putget_port(self):
        om = self.om
        om.models.put('oci://ghcr.io:5000/miraculixx', 'ocireg')
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.url, 'ghcr.io:5000')

    def test_putget_ocidir(self):
        om = self.om
        # -- no image
        om.models.put('ocidir:///tmp/registry/namespace', 'ocireg')
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.repo, None)
        self.assertEqual(str(reg.url), '/tmp/registry')
        # -- image on get
        reg = om.models.get('ocireg', image='myimage:latest')
        self.assertEqual(reg.repo, 'namespace/myimage:latest')
        self.assertEqual(str(reg.url), '/tmp/registry')
        # -- with image
        om.models.put('ocidir:///tmp/registry/namespace/myimage:latest', 'ocireg')
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.repo, 'namespace/myimage:latest')
        self.assertEqual(str(reg.url), '/tmp/registry')
        # -- no image with a long registry path
        om.models.put('ocidir:///tmp/data/artifacts/registry/namespace', 'ocireg')
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.repo, None)
        self.assertEqual(str(reg.url), '/tmp/data/artifacts/registry')
        # -- image on get
        reg = om.models.get('ocireg', image='myimage:latest')
        self.assertEqual(reg.repo, 'namespace/myimage:latest')
        self.assertEqual(str(reg.url), '/tmp/data/artifacts/registry')


if __name__ == '__main__':
    unittest.main()
