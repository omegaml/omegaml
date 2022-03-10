from unittest import TestCase

from omegaml import Omega
from omegaml.tests.util import OmegaTestMixin


class StreamsTestCase(OmegaTestMixin, TestCase):
    # tests om.streams, see minibatch functionality in test_minibatch
    def setUp(self):
        self.om = Omega()
        self.clean()

    def test_streams_get_put(self):
        om = self.om
        stream = om.streams.get('test')
        om.streams.put(dict(foo='bar'), 'test')
        self.assertEqual(stream.buffer().count(), 1)
        meta = om.streams.metadata('test')
        self.assertEqual(meta.kind, 'stream.minibatch')

    def test_streams_emitter(self):
        from minibatch.window import CountWindow
        from minibatch.tests.util import LocalExecutor
        om = self.om
        runner = om.streams.getl('test', size=1, executor=LocalExecutor())
        emitter = runner.make(lambda w: w)
        self.assertIsInstance(emitter, CountWindow)
        om.streams.put(dict(foo='bar'), 'test')
        self.assertEqual(om.streams.get('test').buffer().count(), 1)
        emitter.run(blocking=False)
        self.assertEqual(om.streams.get('test').buffer().count(), 0)




