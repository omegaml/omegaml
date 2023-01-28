from pprint import pprint
from unittest import TestCase

from omegaml import Omega
from omegaml.mixins.store.objinfo import ObjectInformationMixin
from omegaml.tests.util import OmegaTestMixin


class ObjectInformationMixinTests(OmegaTestMixin, TestCase):
    def setUp(self):
        self.om = om = Omega()
        om.datasets.register_mixin(ObjectInformationMixin)
        self.clean()

    def test_summary(self):
        om = self.om
        data = [1, 2, 3]
        om.datasets.put(data, 'test', attributes={
            'docs': 'foobar'
        })
        summary = om.datasets.summary('test')
        self.assertIsInstance(summary, dict)
        self.assertIn('docs', summary)
