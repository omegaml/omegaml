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
            if expected:
                # msg contains the exact message as passed in
                self.assertEqual(df.iloc[0].msg, '{} message'.format(level).lower())
                # text contains the formatted msg
                self.assertNotEqual(df.iloc[0].text, '{} message'.format(level).lower())
                self.assertIn('{} message'.format(level).lower(), df.iloc[0].text)

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
        handler = OmegaLoggingHandler.setup(logger=pylogger, level='DEBUG')
        pylogger.setLevel('DEBUG')
        pylogger.info('info message')
        pylogger.error('error message')
        pylogger.warning('warning message')
        pylogger.debug('debug message')
        df = omlogger.dataset.get()
        self.assertEqual(len(df), 5) # including init
        pylogger.handlers.remove(handler)
        # msg contains the exact message as passed in
        for level in ['INFO', 'ERROR', 'WARNING', 'DEBUG']:
            df = omlogger.dataset.get(filter=dict(levelname=level, name='root'))
            expected = 1
            self.assertEqual(len(df), expected, 'expected 1 message for level {}'.format(level))
            if expected:
                self.assertEqual(df.iloc[0].msg, '{} message'.format(level).lower())
                # text contains the formatted msg
                self.assertNotEqual(df.iloc[0].text, '{} message'.format(level).lower())
                self.assertIn('{} message'.format(level).lower(), df.iloc[0].text)


    def test_named_simplelogger(self):
        """
        test we can get a named logger
        """
        # get a named logger
        logger = self.om.logger.getLogger('foo')
        self.assertIsInstance(logger, OmegaSimpleLogger)
        self.assertNotEqual(logger, self.om.logger)
        self.assertNotEqual(logger.name, self.om.logger.name)
        logger.info('foo')
        df = logger.dataset.get(levelname='INFO')
        self.assertTrue(len(df) == 1)
        self.assertEqual(df.iloc[0]['name'], 'foo')
        # change logger name of the default logger
        self.om.logger.name = 'myname'
        self.om.logger.info('foo')
        df = self.om.logger.dataset.get(filter=dict(levelname='INFO', name='myname'))
        self.assertTrue(len(df) == 1)
        self.assertEqual(df.iloc[-1]['name'], 'myname')

