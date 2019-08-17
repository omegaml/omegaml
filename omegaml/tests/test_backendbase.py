from unittest.case import TestCase

import omegaml as om
from omegaml.backends.basemodel import BaseModelBackend
from omegaml.documents import MDREGISTRY
from omegaml.backends.basedata import BaseDataBackend


class CustomBackendTests(TestCase):

    """
    Test custom backends with new kinds

    Note we are not implemented actually working backends. What we're
    interested here is that the backend API and Metadata storage work.
    """
    def tearDown(self):
        # remove custom backend from implementation not to disturb other tests
        try:
            del om.defaults.OMEGA_STORE_BACKENDS['custom.foo']
            del om.defaults.OMEGA_STORE_BACKENDS['custom.bar']
            MDREGISTRY.KINDS.remove('custom.foo')
            MDREGISTRY.KINDS.remove('custom.bar')
        except:
            pass

    def test_custom_model_backend(self):
        """
        test custom model type 
        """
        om.models.register_backend('custom.foo', CustomModelBackend)
        foo = dict(foo='bar')
        meta = om.models.put(foo, 'footest')
        self.assertIsInstance(meta, om.models._Metadata)
        self.assertEqual(meta.kind, 'custom.foo')
        meta_stored = om.models.metadata('footest')
        self.assertIn('footest', om.models.list())
        self.assertEqual(meta, meta_stored)
        with self.assertRaises(NotImplementedError):
            om.models.get('footest')

    def test_custom_dataset_backend(self):
        """
        test custom dataset type 
        """
        om.datasets.register_backend('custom.bar', CustomDataBackend)
        foo = dict(bar='foo')
        meta = om.datasets.put(foo, 'bartest')
        self.assertIsInstance(meta, om.datasets._Metadata)
        self.assertEqual(meta.kind, 'custom.bar')
        meta_stored = om.datasets.metadata('bartest')
        self.assertIn('bartest', om.datasets.list())
        self.assertEqual(meta, meta_stored)
        with self.assertRaises(NotImplementedError):
            om.datasets.get('bartest')


class CustomModelBackend(BaseModelBackend):

    """
    Minimalist model backend
    """

    @classmethod
    def supports(self, obj, name, **kwargs):
        return isinstance(obj, dict) and 'foo' in obj

    def put_model(self, obj, name, attributes=None):
        kind = 'custom.foo'
        return self.model_store.make_metadata(name, kind, bucket=None,
                                              prefix=None,
                                              attributes=attributes).save()


class CustomDataBackend(BaseDataBackend):

    """
    Minimalist dataset backend
    """

    @classmethod
    def supports(self, obj, name, **kwargs):
        return isinstance(obj, dict) and 'bar' in obj

    def put(self, obj, name, attributes=None):
        kind = 'custom.bar'
        return self.model_store.make_metadata(name, kind, bucket=None,
                                              prefix=None,
                                              attributes=attributes).save()
