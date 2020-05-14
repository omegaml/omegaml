import logging
import unittest

from omegaml import Omega
from omegaml.store.logging import OmegaSimpleLogger, OmegaLoggingHandler
from omegaml.tests.util import OmegaTestMixin


class OmegaLoggingTests(OmegaTestMixin, unittest.TestCase):
    def setUp(self):
        self.om = Omega()
        self.clean()
        self._reset_log()

    def tearDown(self):
        self.assertTrue(all(m.name is not None for m in self.om.datasets.list(raw=True)))

    def _reset_log(self):
        self.om.datasets.drop('.omega/logs', force=True)

    def test_simple_logger(self):
        logger = self.om.logger
        self.assertIsInstance(logger, OmegaSimpleLogger)
        logger.setLevel('DEBUG')
        logger.info('info message')
        logger.error('error message')
        logger.debug('debug message')
        logger.warning('warning message')
        logger.critical('critical message')
        for level in OmegaSimpleLogger.levels:
            expected = 1 if level != 'QUIET' else 0
            df = logger.dataset.get(levelname=level)
            self.assertTrue(len(df) == expected, 'level {} did not have a record'.format(level))

    def test_simple_logger_level(self):
        logger = self.om.logger
        self.assertIsInstance(logger, OmegaSimpleLogger)
        logger.setLevel('INFO')
        logger.info('info message')
        logger.debug('error message')
        df = logger.dataset.get(levelname='DEBUG')
        self.assertTrue(len(df) == 0)
        df = logger.dataset.get(levelname='INFO')
        self.assertTrue(len(df) == 1)

    def test_simple_logger_quiet(self):
        logger = self.om.logger
        self.assertIsInstance(logger, OmegaSimpleLogger)
        logger.info('initialize') # need this to initialize
        logger.setLevel('QUIET')
        logger.error('info message')
        logger.debug('error message')
        df = logger.dataset.get(levelname='INFO')
        self.assertTrue(len(df) == 1)
        df = logger.dataset.get(levelname='DEBUG')
        self.assertTrue(len(df) == 0)
        df = logger.dataset.get(levelname='ERROR')
        self.assertTrue(len(df) == 0)

    def test_loghandler(self):
        pylogger = logging.getLogger()
        omlogger = self.om.logger
        handler = OmegaLoggingHandler.setup(logger=pylogger)
        pylogger.info('test')
        df = omlogger.dataset.get(levelname='INFO')
        self.assertTrue(len(df) == 1) # includes initialization message
        pylogger.handlers.remove(handler)




