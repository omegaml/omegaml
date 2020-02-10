import pathlib
from unittest import TestCase, skipIf, skip

from omegaml import Omega
from omegaml.backends.tensorflow.tfdataset import TFDatasetBackend
from omegaml.tests.util import tf_in_eager_execution, tf_perhaps_eager_execution, OmegaTestMixin

# check https://www.tensorflow.org/datasets/api_docs/python/tfds/testing/run_in_graph_and_eager_modes
@skip("requires eager mode which must be enabled once for the whole python session")
class TensorflowDatasetBackendTests(OmegaTestMixin, TestCase):
    def setUp(self):
        import os
        os.environ['TF_EAGER'] = '1'
        tf_perhaps_eager_execution()
        self.om = Omega()
        self.om.models.register_backend(TFDatasetBackend.KIND, TFDatasetBackend)
        self.clean()

    def get_image_ds(self):
        import tensorflow as tf
        from tensorflow.python.data.experimental import AUTOTUNE

        data_root_orig = tf.keras.utils.get_file('flower_photos',
                                                 'https://storage.googleapis.com/download.tensorflow.org/example_images/flower_photos.tgz',
                                                 untar=True)
        data_root = pathlib.Path(data_root_orig)

        all_image_paths = list(data_root.glob('*/*'))
        all_image_paths = [str(path) for path in all_image_paths]

        def load_and_preprocess_image(path):
            image = tf.read_file(path)
            return image

        path_ds = tf.data.Dataset.from_tensor_slices(all_image_paths)
        image_ds = path_ds.map(load_and_preprocess_image, num_parallel_calls=AUTOTUNE)
        return image_ds

    def test_save_dataset(self):
        import tensorflow as tf
        ds = self.get_image_ds()
        for img in ds.take(1):
            print(img.numpy())
            break





