from time import sleep
from unittest import TestCase

from multiprocessing import Process

from omegaml import Omega
from omegaml.util import delete_database
from minibatch import Stream, Buffer, connectdb, stream


class MiniBatchTests(TestCase):
    def setUp(self):
        delete_database()
        self.om = Omega()
        db = self.om.datasets.mongodb
        self.url =self.om.mongo_url + '?authSource=admin'
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

        def consumer():
            # note the stream decorator blocks the consumer and runs the decorated
            # function asynchronously upon the window criteria is satisfied
            @streaming('test', size=2, url=self.url, keep=True)
            def myprocess(window):
                try:
                    om = Omega()
                    db = om.datasets.mongodb
                    db.processed.insert_one({'data': window.data or {}})
                except Exception as e:
                    print(e)
                return window
        # start stream consumer
        proc = Process(target=consumer)
        proc.start()
        # fill stream
        s = stream('test', url=self.url)
        for i in range(10):
            s.append({'index': i})
        # give it some time to process
        sleep(5)
        proc.terminate()
        # expect 5 entries, each of length 2
        data = list(doc for doc in self.om.datasets.mongodb.processed.find())
        count = len(data)
        self.assertEqual(count, 5)
        self.assertTrue(all(len(w) == 2 for w in data))

    def test_timed_window(self):
        """
        Test batch windows of fixed sizes work ok
        """
        from minibatch import streaming

        def consumer():
            # note the stream decorator blocks the consumer and runs the decorated
            # function asynchronously upon the window criteria is satisfied
            @streaming('test', interval=1, keep=True, url=self.url)
            def myprocess(window):
                try:
                    om = Omega()
                    db = om.datasets.mongodb
                    db.processed.insert_one({'data': window.data or {}})
                except Exception as e:
                    print(e)
                return window
        # start stream consumer
        proc = Process(target=consumer)
        proc.start()
        # fill stream
        s = stream('test', url=self.url)
        for i in range(10):
            s.append({'index': i})
            sleep(.5)
        # give it some time to process
        sleep(5)
        proc.terminate()
        # expect at least 5 entries (10 x .5 = 5 seconds), each of length 1-2
        data = list(doc for doc in self.om.datasets.mongodb.processed.find())
        count = len(data)
        self.assertGreater(count, 5)
        self.assertTrue(all(len(w) >= 2 for w in data))

    def test_timed_window_relaxed(self):
        """
        Test batch windows of fixed sizes work ok
        """
        from minibatch import streaming

        def consumer():
            # note the stream decorator blocks the consumer and runs the decorated
            # function asynchronously upon the window criteria is satisfied
            @streaming('test', interval=1, relaxed=True, keep=True, url=self.url)
            def myprocess(window):
                try:
                    om = Omega()
                    db = om.datasets.mongodb
                    db.processed.insert_one({'data': window.data or {}})
                except Exception as e:
                    print(e)
                return window
        # start stream consumer
        proc = Process(target=consumer)
        proc.start()
        # fill stream
        s = stream('test', url=self.url)
        for i in range(10):
            s.append({'index': i})
            sleep(.5)
        # give it some time to process
        sleep(5)
        proc.terminate()
        # expect at least 5 entries (10 x .5 = 5 seconds), each of length 1-2
        data = list(doc for doc in self.om.datasets.mongodb.processed.find())
        count = len(data)
        self.assertGreater(count, 5)
        self.assertTrue(all(len(w) >= 2 for w in data))

