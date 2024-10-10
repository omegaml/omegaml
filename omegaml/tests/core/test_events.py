from unittest import TestCase

import logging
from omegaml import Omega
from omegaml.client.lunamon import LunaMonitor, OmegaMonitors
from time import sleep


class EventsTestClass(TestCase):
    def setUp(self):
        self.om = Omega()
        logger = logging.getLogger('omegaml.util.monitor')
        # add to see debugging output
        # logger.setLevel(logging.DEBUG)
        # logger.addHandler(logging.StreamHandler())

    def tearDown(self):
        pass

    def test_connection_checks(self):
        monitor = LunaMonitor(checks=OmegaMonitors.on(self.om), interval=.1)
        reports = []
        monitor.notify(on_status=lambda status: reports.append(status))
        sleep(2)
        self.assertTrue(len(reports) > 0)
        monitor.assert_ok('database', timeout=1)
        monitor.assert_ok('runtime', timeout=1)
        monitor.assert_ok(timeout=5)
        self.assertTrue(monitor.healthy())
        self.assertTrue(monitor.healthy('database'))
        self.assertTrue(all(s == 'ok' for c, s in monitor.status().items()))
        self.assertTrue(monitor.status('health') == 'ok')
        # pprint(monitor.status(data=True))
        # {'broker': {'data': None,
        #             'elapsed': 3.5762786865234375e-06,
        #             'error': '<empty>',
        #             'message': 'check broker was successful',
        #             'status': 'ok',
        #             'timestamp': datetime.datetime(2024, 2, 2, 12, 45, 56, 395485)},
        #  'database': {'data': None,
        #               'elapsed': 0.0022907257080078125,
        #               'error': '<empty>',
        #               'message': 'check database was successful',
        #               'status': 'ok',
        #               'timestamp': datetime.datetime(2024, 2, 2, 12, 45, 56, 397465)},
        #  'monitor': {'data': None,
        #              'elapsed': None,
        #              'error': '<empty>',
        #              'message': None,
        #              'status': 'ok',
        #              'timestamp': datetime.datetime(2024, 2, 2, 12, 45, 56, 395082)},
        #  'runtime': {'data': None,
        #              'elapsed': 0.008479595184326172,
        #              'error': '<empty>',
        #              'message': 'check runtime was successful',
        #              'status': 'ok',
        #              'timestamp': datetime.datetime(2024, 2, 2, 12, 45, 56, 404147)},
        #  'stores': {'data': None,
        #             'elapsed': 0.0018122196197509766,
        #             'error': '<empty>',
        #             'message': 'check stores was successful',
        #             'status': 'ok',
        #             'timestamp': datetime.datetime(2024, 2, 2, 12, 45, 56, 397746)}}
        monitor.stop()
