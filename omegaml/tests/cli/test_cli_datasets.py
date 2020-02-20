from unittest import TestCase

from numpy.testing import assert_array_equal
from pandas.util.testing import assert_frame_equal

from omegaml import Omega
from omegaml.tests.cli.scenarios import CliTestScenarios
from omegaml.tests.util import OmegaTestMixin
from omegaml.util import temp_filename

import pandas as pd

class CliModelsTest(CliTestScenarios, OmegaTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.om = Omega()
        self.clean()

    def test_cli_datasets_help(self):
        self.cli('help datasets')

    def test_cli_datasets_list(self):
        # start with empty datasets
        self.cli('datasets list')
        expected = self.pretend_log([])
        self.assertLogEqual('info', expected)
        # add a test dataset
        self.make_dataset_from_dataframe('testds')
        self.cli('datasets list', new_start=True)
        expected = self.pretend_log(['testds'])
        self.assertLogEqual('info', expected)
        # add another one, use pattern matching
        self.make_dataset_from_dataframe('foobar')
        # -- just on one
        self.cli('datasets list test*', new_start=True)
        expected = self.pretend_log(['testds'])
        self.assertLogEqual('info', expected)
        # -- on the other
        self.cli('datasets list foo*', new_start=True)
        expected = self.pretend_log(['foobar'])
        self.assertLogEqual('info', expected)
        # match both
        self.cli('datasets list foo.*|test.* -E', new_start=True)
        expected = self.pretend_log(['foobar', 'testds'])
        self.assertLogEqual('info', expected)

    def test_cli_datasets_put(self):
        # write a csv, read back
        fn = temp_filename(ext='csv')
        df = self.create_local_csv(fn)
        self.cli(f'datasets put {fn} foobar')
        self.assertLogContains('info', 'Metadata(')
        self.assertLogContains('info', 'kind=pandas.dfrows')
        dfx = self.om.datasets.get('foobar')
        assert_frame_equal(df, dfx)
        # write a csv, read back, use custom sep
        fn = temp_filename(ext='csv')
        df = self.create_local_csv(fn, sep=';')
        self.cli(f'datasets put {fn} foxbaz --csv sep=;')
        self.assertLogContains('info', 'Metadata(')
        self.assertLogContains('info', 'kind=pandas.dfrows')
        dfx = self.om.datasets.get('foxbaz')
        assert_frame_equal(df, dfx)
        # write some other file
        fn = temp_filename(ext='binary')
        df = self.create_local_csv(fn)
        self.cli(f'datasets put {fn} binary', new_start=True)
        print(self.get_log('info'))
        self.assertLogContains('info', 'Metadata(')
        self.assertLogContains('info', 'kind=python.file')
        with open(fn, 'rb') as fin:
            expected = fin.read()
        data = self.om.datasets.get('binary').read()
        self.assertEqual(expected, data)
        # write image file
        fn = temp_filename(ext='jpg')
        img = self.create_local_image_file(fn)
        self.cli(f'datasets put {fn} image', new_start=True)
        self.assertLogContains('info', 'Metadata(')
        self.assertLogContains('info', 'kind=ndarray.bin')
        data = self.om.datasets.get('image')
        assert_array_equal(data, img)

    def test_cli_datasets_get(self):
        # write a csv, read back
        fn = temp_filename(ext='csv')
        self.make_dataset_from_dataframe('test')
        self.cli(f'datasets get test {fn}')
        df = pd.read_csv(fn)
        expected = self.om.datasets.get('test')
        assert_frame_equal(df, expected)
        # write a csv, read back with options
        fn = temp_filename(ext='csv')
        self.make_dataset_from_dataframe('test-sep')
        self.cli(f'datasets get test-sep {fn} --csv sep=; --csv columns=x,')
        df = pd.read_csv(fn, sep=';')
        expected = self.om.datasets.get('test')[['x']]
        assert_frame_equal(expected, df)

    def test_cli_datasets_drop(self):
        self.make_dataset_from_dataframe('test')
        self.assertIn('test', self.om.datasets.list())
        self.cli('datasets drop test')
        self.assertNotIn('test', self.om.datasets.list())

    def test_cli_datasets_metadata(self):
        self.make_dataset_from_dataframe('test')
        self.cli('datasets metadata test')
        expected = self.pretend_log('"kind": "pandas.dfrows"')
        self.assertLogContains('info', expected)
        expected = self.pretend_log('"name": "test"')
        self.assertLogContains('info', expected)












