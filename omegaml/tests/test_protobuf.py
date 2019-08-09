import os
from unittest import TestCase

from omegaml import Omega
from omegaml.backends.tensorflow.protobufobj import ProtobufDataBackend
from omegaml.tests.util import OmegaTestMixin, tf_perhaps_eager_execution


# tensorflow example adopted from https://www.tensorflow.org/tutorials/load_data/tf_records

class ProtobufDataBackendTests(OmegaTestMixin, TestCase):
    def setUp(self):
        self.om = Omega()
        self.om.datasets.register_backend(ProtobufDataBackend.KIND, ProtobufDataBackend)
        self.clean()
        self._images = None
        tf_perhaps_eager_execution()

    @property
    def images(self):
        import tensorflow as tf
        if self._images is None:
            IMAGES = [
                (0,
                 'https://storage.googleapis.com/download.tensorflow.org/example_images/320px-Felis_catus-cat_on_snow.jpg')
            ]
            self._images = []
            for label, imgurl in IMAGES:
                path = tf.keras.utils.get_file(imgurl.split('/')[-1], imgurl)
                self._images.append((label, path))
        return self._images

    def create_example(self, imgpath, label):
        import tensorflow as tf
        with open(imgpath, 'rb') as fin:
            image_string = fin.read()
            image_tensor = tf.image.decode_jpeg(image_string)
        # if not in eager we need to evaluate the tensor first
        if not tf.executing_eagerly():
            with tf.Session() as sess:
                image_shape = sess.run(image_tensor).shape
        else:
            image_shape = image_tensor.shape
        # create feature record
        feature = {
            'height': _int64_feature(image_shape[0]),
            'width': _int64_feature(image_shape[1]),
            'depth': _int64_feature(image_shape[2]),
            'label': _int64_feature(label),
            'image_raw': _bytes_feature(image_string),
        }
        return tf.train.Example(features=tf.train.Features(feature=feature))

    def test_image_protobuf_get_put(self):
        import tensorflow as tf
        om = self.om
        for label, imgpath in self.images:
            example = self.create_example(imgpath, label)
            filename = os.path.basename(imgpath)
            entryname = 'images/{label}/{filename}.pbf'
            meta = om.datasets.put(example, entryname)
            self.assertEqual(meta.kind, ProtobufDataBackend.KIND)
            data = om.datasets.get(entryname)
            self.assertIsInstance(data, tf.train.Example)


# adopted from https://github.com/tensorflow/tensorflow/blob/master/tensorflow/examples/how_tos/reading_data/convert_to_records.py
def _bytes_feature(value):
    """Returns a bytes_list from a string / byte."""
    import tensorflow as tf
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))


def _float_feature(value):
    """Returns a float_list from a float / double."""
    import tensorflow as tf
    return tf.train.Feature(float_list=tf.train.FloatList(value=[value]))


def _int64_feature(value):
    """Returns an int64_list from a bool / enum / int / uint."""
    import tensorflow as tf
    return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))
