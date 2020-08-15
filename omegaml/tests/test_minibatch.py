
from multiprocessing import Process, Queue
from unittest import TestCase

from minibatch import Buffer, connectdb, stream
from minibatch.contrib.omegaml import DatasetSink
from time import sleep

from omegaml import Omega
from omegaml.util import delete_database


class MiniBatchTests(TestCase):
    def setUp(self):
        delete_database()
        self.om = Omega()
        db = self.om.datasets.mongodb
        self.url = self.om.mongo_url + '?authSource=admin'
        connectdb(url=self.url)

    def test_stream(self):
        """
        Test a stream writes to a buffer
        """
        from minibatch import stream
        om = self.om
        om.datasets.mongodb
        s = stream('test', url=self.url)
        s.append({'foo': 'bar1'})
        s.append({'foo': 'bar2'})
        count = len(list(doc for doc in Buffer.objects.all()))
        self.assertEqual(count, 2)

    def test_fixed_size(self):
        """
        Test batch windows of fixed sizes work ok
        """
        from minibatch import streaming, stream

        def consumer(q, url):
            # note the stream decorator blocks the consumer and runs the decorated
            # function asynchronously upon the window criteria is satisfied
            om = Omega(mongo_url=url)

            @streaming('test', size=2, url=url, keep=True, queue=q,
                       sink=DatasetSink(om, 'consumer'))
            def myprocess(window):
                return {'myprocess': True, 'data': window.data}

        # start stream and consumer
        s = stream('test', url=self.url)
        q = Queue()
        proc = Process(target=consumer, args=(q, self.url))
        proc.start()
        # fill stream
        for i in range(10):
            s.append({'index': i})
        # give it some time to process
        sleep(5)
        q.put(True)
        proc.join()
        # expect 5 entries, each of length 2
        windows = list(doc for doc in self.om.datasets.collection('consumer').find())
        self.assertEqual(len(windows), 5)
        self.assertTrue(all(len(w['data']) == 2 for w in windows))

    def test_timed_window(self):
        """
        Test timed windows work ok
        """
        from minibatch import streaming

        def consumer(q, url):
            # note the stream decorator blocks the consumer and runs the decorated
            # function asynchronously upon the window criteria is satisfied
            om = Omega(mongo_url=url)

            @streaming('test', interval=1, keep=True, url=url, queue=q,
                       sink=DatasetSink(om, 'consumer'))
            def myprocess(window):
                return {'myprocess': True, 'data': window.data}

        # start stream and consumer
        q = Queue()
        s = stream('test', url=self.url)
        proc = Process(target=consumer, args=(q, self.url,))
        proc.start()
        # fill stream
        for i in range(10):
            s.append({'index': i})
            sleep(.5)
        # give it some time to process
        sleep(5)
        q.put(True)
        proc.join()
        # expect at least 5 entries (10 x .5 = 5 seconds), each of length 1-2
        windows = list(doc for doc in self.om.datasets.collection('consumer').find())
        self.assertGreater(len(windows), 5)
        print(windows)
        self.assertTrue(all(len(w['data']) >= 1 for w in windows))

    def test_timed_window_relaxed(self):
        """
        Test relaxed time windows work ok
        """
        from minibatch import streaming

        def consumer(q, url):
            # note the stream decorator blocks the consumer and runs the decorated
            # function asynchronously upon the window criteria is satisfied
            om = Omega(mongo_url=url)

            @streaming('test', interval=1, relaxed=True,
                       keep=True, url=url, queue=q,
                       sink=DatasetSink(om, 'consumer'))
            def myprocess(window):
                return {'myprocess': True, 'data': window.data}

        # start stream and consumer
        s = stream('test', url=self.url)
        q = Queue()
        proc = Process(target=consumer, args=(q, self.url,))
        proc.start()
        # fill stream
        for i in range(10):
            s.append({'index': i})
            sleep(.5)
        # give it some time to process
        sleep(5)
        q.put(True)
        proc.join()
        # expect at least 5 entries (10 x .5 = 5 seconds), each of length 1-2
        windows = list(doc for doc in self.om.datasets.collection('consumer').find())
        self.assertGreater(len(windows), 5)
        self.assertTrue(all(len(w['data']) >= 1 for w in windows))
