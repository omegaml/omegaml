from collections import defaultdict
from unittest import TestCase

from sklearn.linear_model import LinearRegression

from omegaml import Omega
from omegaml.client.cli import main
from omegaml.tests.util import OmegaTestMixin


class ClientCliTest(OmegaTestMixin, TestCase):
    def setUp(self):
        self.om = Omega()
        self.clean()

    def test_cli_models_list(self):
        # start with an empty list
        argv = 'models list'.split(' ')
        parser = main(argv=argv, logger=get_test_logger())
        expected = ([],)
        data = parser.logger.data['info']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0], expected)
        # add a model, see that we get it back
        reg = LinearRegression()
        self.om.models.put(reg, 'reg')
        parser = main(argv=argv, logger=get_test_logger())
        expected = (['reg'],)
        data = parser.logger.data['info']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0], expected)
        # check we can get back a Metadata object
        argv = 'models list --raw'.split(' ')
        parser = main(argv=argv, logger=get_test_logger())
        data = parser.logger.data['info']
        self.assertTrue(str(data[0][0][0]).startswith('Metadata('))


def get_test_logger():
    class TestLogger:
        data = defaultdict(list)

        def info(self, *args):
            self.data['info'].append(args)

        def error(self, *args):
            self.data['error'].append(args)

        def debug(self, *args):
            self.data['debug'].append(args)

    return TestLogger()
