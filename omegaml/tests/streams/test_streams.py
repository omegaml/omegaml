from unittest import TestCase

from unittest.mock import patch, MagicMock

from omegaml import Omega
from omegaml.tests.util import OmegaTestMixin


class StreamsTestCase(OmegaTestMixin, TestCase):
    # tests om.streams, see minibatch functionality in test_minibatch
    def setUp(self):
        self.om = Omega()
        self.clean()

    @classmethod
    def tearDownClass(cls):
        pass

    def test_streams_get_put(self):
        om = self.om
        stream = om.streams.get('test')
        om.streams.put(dict(foo='bar'), 'test')
        self.assertEqual(stream.buffer().count(), 1)
        meta = om.streams.metadata('test')
        self.assertEqual(meta.kind, 'stream.minibatch')

    def test_streams_autoattach_runtime(self):
        om = self.om
        # specify streaming and source kwargs
        stream = om.streams.get('test',
                                streaming=dict(window=5),
                                source=(om, 'runtime', dict(events=['*'])),
                                autoattach=False,
                                )
        stream.stop()
        meta = om.streams.metadata('test')
        self.assertEqual(meta.kind_meta, {
            'stream': {
                'name': 'omegaml.streams/.test.stream',
                'stream_kwargs': {},
                'streaming_kwargs': {'window': 5}
            },
            'attach': {
                'source': 'runtime',
                'source_kwargs': {'events': ['*']}
            }
        })
        with patch('minibatch.contrib.celery.CeleryEventSource', MagicMock()) as mx_stream:
            stream = om.streams.get('test')
            self.assertEqual(mx_stream.call_args[1]['events'], ['*'])

    def test_streams_autoattach_dataset(self):
        om = self.om
        # specify streaming and source kwargs
        om.datasets.put([1, 2, 3], 'foobar')
        stream = om.streams.get('test',
                                streaming=dict(window=5),
                                source=(om, 'foobar'),
                                autoattach=False,
                                )
        meta = om.streams.metadata('test')
        self.assertEqual(meta.kind_meta, {
            'stream': {
                'name': 'omegaml.streams/.test.stream',
                'stream_kwargs': {},
                'streaming_kwargs': {'window': 5}
            },
            'attach': {
                'source': 'foobar',
                'source_kwargs': {}
            }
        })
        # check runtime is attached automatically
        with patch('minibatch.contrib.omegaml.DatasetSource', MagicMock()) as mx_stream:
            stream = om.streams.get('test')
            mx_stream.assert_called_once()

    def test_streams_autoclean(self):
        om = self.om
        # specify streaming and source kwargs
        om.datasets.put([1, 2, 3], 'foobar')
        stream = om.streams.get('test',
                                streaming=dict(window=5),
                                source=(om, 'foobar'),
                                autoattach=False,
                                max_age=.1,
                                )
        meta = om.streams.metadata('test')
        stream.stop()
        self.assertEqual(meta.kind_meta, {
            'stream': {
                'name': 'omegaml.streams/.test.stream',
                'stream_kwargs': {'max_age': .1},
                'streaming_kwargs': {'window': 5}
            },
            'attach': {
                'source': 'foobar',
                'source_kwargs': {}
            }
        })
        # check runtime is attached automatically
        with patch('minibatch.stream', MagicMock()) as mx_stream:
            stream = om.streams.get('test')
            stream.stop()
            mx_stream.assert_called_once()
            self.assertEqual(mx_stream.call_args.kwargs['max_age'], .1)
        return

    def test_streams_attach_runtime(self):
        om = self.om
        with self.assertRaises(ValueError):
            om.streams.get('test', source='foobar')
        # test we can attach to a dataset
        om.datasets.put([1, 2, 3], 'foobar')
        stream = om.streams.get('test', source='foobar')
        om.datasets.put([1, 2, 3], 'foobar')
        self.assertEqual(len(list(stream.buffer())), 1)
        stream.stop()
        stream.clear()
        # test we can attach to the runtime
        with patch('minibatch.contrib.celery.CeleryEventSource', MagicMock()) as mx_stream:
            stream = om.streams.get('test', source='runtime')
            mx_stream.assert_called_once()
            stream.stop()
            stream.clear()

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
