from unittest import TestCase

from omegaml import Omega
from omegaml.backends.npndarray import NumpyNDArrayBackend

import numpy as np


class NumpyNDArrayBackendTests(TestCase):
    def setUp(self):
        om = self.om = Omega()
        om.datasets.register_backend(NumpyNDArrayBackend.KIND, NumpyNDArrayBackend)

    def test_store_ndarray(self):
        om = self.om
        arr = np.random.randint(0, 255, (768, 1204), dtype=np.uint8)
        # store
        meta = om.datasets.put(arr, 'ndarray-test')
        self.assertIsNotNone(meta)
        self.assertEqual(meta.kind, 'ndarray.bin')
        self.assertEqual(meta.name, 'ndarray-test')
        self.assertIn('dtype', meta.kind_meta)
        self.assertIn('shape', meta.kind_meta)
        # get back
        data = om.datasets.get('ndarray-test')
        self.assertIsNotNone(data)
        self.assertEqual(data.shape, arr.shape)
        self.assertEqual(data.dtype, arr.dtype)
