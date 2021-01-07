import string
from collections import defaultdict

import numpy as np
import os
import pandas as pd
import sys
from nbformat import v4
from sklearn.linear_model import LinearRegression

from omegaml.client import cli


class CliTestScenarios:
    """TestCase plugin with common environment scenarios"""

    def setUp(self):
        super().setUp()
        self.pretend_logger = None

    def get_test_logger(self):
        """
        create a test logger that captures info, error, debug output

        Returns:
            a logger object, use logger.data['info|error|debug'] to get
            respective logger output by cli
        """

        class TestLogger:
            data = defaultdict(list)

            def info(self, *args):
                self.data['info'].append(args)

            def error(self, *args):
                self.data['error'].append(args)

            def debug(self, *args):
                self.data['debug'].append(args)

            def clear(self):
                self.data = defaultdict(list)

        return TestLogger()

    def pretend_log(self, *args, start_empty=False, level='info'):
        """
        return what would be written in log

        Use to generate expected test output feasible for assertLogEqual
        This way you don't need to understand the internal of TestLogger

        Args:
            args: what would be passed to logger.info(args)

        Usage:
            you would like to test if the cli writes a log entry of some kind:

            # you expect the cli to issue a log statement like this
            logger.info('there were 0 items in the list')

            # code to write
            expected = self.pretend_log('there were 0 items in the list')
            self.assertLogEqual('info', expected)

        Returns:
            the actual log entry that would be written
        """
        if self.pretend_logger is None:
            self.pretend_logger = self.get_test_logger()
        logger = self.pretend_logger
        if start_empty:
            logger.clear()
        level_logger = getattr(logger, level)
        level_logger(*args)
        return logger.data[level]

    def get_log(self, level):
        return self.cli_logger.data[level]

    def assertLogSize(self, level, size):
        """ assert log of level has number of entries (lines) """
        self.assertEqual(size, len(self.get_log(level)))

    def assertLogEqual(self, level, expected):
        """ assert log of level has expected contents """
        self.assertEqual(expected, self.get_log(level))

    def assertLogContains(self, level, expected, compare_as=str):
        """
        assert the log level contains some content

        Each log entry is compared to expected, if no match is found
        will raise AssertionError. By default the comparision is
        a test of str(expected) in str(log) for every entry in expected
        and log respectively. To compare as object, pass compare_as=object

        Args:
            level: the log level
            expected: the expected entry(ies), as returned by pretend_log(). if
               a string is passed will be replaced with the result of
               pretend_log(level, expected)
            compare_as: type or callable for casting entries, defaults to str

        Raises:
            AssertionError if no match is found
        """
        if isinstance(expected, str):
            expected = self.pretend_log(expected, level=level)[-1:]
        data = self.get_log(level)
        if compare_as is not object:
            # unpack log entries, not a log entry is a *args tuple
            # hence we need to iterate that to get each value
            expected = [compare_as(v) for args in expected for v in args]
            data = [compare_as(v) for args in data for v in args]
        match = False
        for e in expected:
            for d in data:
                match |= e in d
        if not match:
            raise AssertionError(f'{expected} is not in {data} compared as {compare_as}')

    def cli(self, argv, new_start=False, **kwargs):
        self.cli_logger = self.get_test_logger()
        if new_start:
            self.cli_logger.clear()
            self.pretend_logger.clear() if self.pretend_logger else None
        if isinstance(argv, str):
            argv = argv.split(' ')
        self.cli_parser = cli.main(argv=argv, logger=self.cli_logger, **kwargs)
        return self.cli_parser

    def make_model(self, name):
        """
        create and store a model

        Args:
            name: the model name

        Returns:
            Metadata of the model
        """
        om = self.om
        # add a model, see that we get it back
        reg = LinearRegression()
        return om.models.put(reg, 'reg')

    def make_dataset_from_dataframe(self, name, N=100, m=2, b=0):
        """
        create and store a pandas dataframe

        Args:
            name: the dataset name

        Returns:
            Metadata of the dataset
        """
        import pandas as pd
        df = pd.DataFrame({
            'x': range(N),
            'y': range(N)
        })
        df['y'] = df['x'] * m + b
        return self.om.datasets.put(df, name, append=False)

    def create_local_csv(self, path, size=(100, 2), sep=','):
        """
        create a local dataset

        Args:
            name:
            size:

        Returns:

        """
        data = np.random.randint(0, 100, size=size)
        df = pd.DataFrame(data, columns=list(string.ascii_uppercase[0:size[1]]))
        df.to_csv(path, index=None, sep=sep)
        return df

    def create_local_image_file(self, path):
        from imageio import imsave
        import numpy as np
        img = np.zeros([100, 100, 3], dtype=np.uint8)
        img.fill(255)
        imsave(path, img)
        return img

    def create_job(self, name):
        cells = []
        code = "print('hello')"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put the notebook
        return self.om.jobs.put(notebook, name)

    def get_package_path(self):
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'helloworld'))
        return pkgpath

