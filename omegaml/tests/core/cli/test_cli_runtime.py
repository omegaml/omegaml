from unittest import TestCase
from unittest.mock import patch, MagicMock

import numpy as np
from numpy.testing import assert_almost_equal
from pathlib import Path
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV

from omegaml import Omega
from omegaml.tests.core.cli.scenarios import CliTestScenarios
from omegaml.tests.util import OmegaTestMixin


class CliRuntimeTests(CliTestScenarios, OmegaTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.om = Omega()
        self.clean()

    def test_cli_runtime_model_fit_predict(self):
        self.make_model('reg')
        reg = self.om.models.get('reg')
        self.make_dataset_from_dataframe('test', N=10)
        # -- fit the model
        self.cli('runtime model reg fit test[x] test[y]')
        self.assertLogContains('info', 'Metadata')
        # -- run a prediction, we get back actual data
        self.cli('runtime model reg predict test[x]', new_start=True)
        self.assertLogContains('info', '[[')
        self.assertIsInstance(self.get_log('info')[0][0], np.ndarray)
        # -- run a prediction, we store the results
        self.cli('runtime model reg predict test[x] --result predictions')
        #    expect metadata since we ask to write data to predictions
        self.assertLogContains('info', 'Metadata')
        df_expect = self.om.datasets.get('test')['y']
        #    check the data has actually been stored as requested
        df_pred = self.om.datasets.get('predictions')
        self.assertIsNotNone(df_pred)
        self.assertEqual(len(df_expect), len(df_pred))

    def test_cli_runtime_model_gridsearch(self):
        X, y = make_classification()
        logreg = LogisticRegression(solver='liblinear')
        self.om.models.put(logreg, 'logreg')
        # perform gridsearch on runtime
        self.om.datasets.put(X, 'testX')
        self.om.datasets.put(y, 'testY')
        self.cli('runtime model logreg gridsearch testX testY --param C=[.1,.5,1.0]')
        model_meta = self.om.models.metadata('logreg')
        self.assertIn('gridsearch', model_meta.attributes)
        gsmodel_name = model_meta.attributes['gridsearch'][0]['gsModel']
        gsmodel = self.om.models.get(gsmodel_name)
        self.assertIsInstance(gsmodel, GridSearchCV)

    def test_cli_runtime_script_run(self):
        pkgpath = self.get_package_path()
        self.cli(f'scripts put {pkgpath} helloworld')
        self.assertLogContains('info', 'Metadata')
        # run without kwargs
        self.cli('runtime script helloworld run', new_start=True)
        self.assertLogContains('info', 'hello from helloworld')
        # with kwargs
        self.cli('runtime script helloworld run foo=bar', new_start=True)
        self.assertLogContains('info', '"foo": "bar"')

    def test_cli_runtime_model_fit_predict_versions(self):
        self.make_model('reg')
        reg = self.om.models.get('reg')
        self.make_dataset_from_dataframe('test', N=10, m=2, b=0)
        self.make_dataset_from_dataframe('test2', N=10, m=5, b=10)
        # -- fit the model
        self.cli('runtime model reg fit test[x] test[y]')
        self.cli('runtime model reg fit test2[x] test2[y]')
        # -- run a prediction, we store the results, by previous pointer
        self.cli('runtime model reg^ predict test[x] --result pred1')
        self.cli('runtime model reg predict test[x] --result pred2')
        df_expect1 = self.om.datasets.get('test')['y'].values
        df_expect2 = self.om.datasets.get('test2')['y'].values
        #    check the data has actually been stored as requested
        df_pred1 = self.om.datasets.get('pred1').flatten()
        df_pred2 = self.om.datasets.get('pred2').flatten()
        assert_almost_equal(df_expect1, df_pred1, decimal=1)
        assert_almost_equal(df_expect2, df_pred2, decimal=1)

    def test_cli_export_import_compressed(self):
        om = self.om
        self.make_model('reg')
        self.make_dataset_from_dataframe('sample')
        # export into a compressed archive
        self.cli('runtime export --compress --path=/tmp/testcli')
        expfile = self.get_log('info', as_text=True)[-1]
        self.assertTrue(Path(expfile).exists())
        # delete everything, import
        self.clean()
        self.cli(f'runtime import --path={expfile}')
        self.assertIn('reg', om.models.list())
        self.assertIn('sample', om.datasets.list())
        # import and promote model (twice to get 2 versions)
        self.clean()
        self.cli(f'runtime import --promote --path={expfile} models/*')
        self.cli(f'runtime import --promote --path={expfile} models/*')
        self.assertEqual(len(om.models.revisions('reg')), 2)

    def test_cli_export_import_path(self):
        om = self.om
        self.make_model('reg')
        self.make_dataset_from_dataframe('sample')
        # export into a compressed archive
        self.cli('runtime export --path=/tmp/testcli')
        expfile = self.get_log('info', as_text=True)[-1]
        self.assertTrue(Path(expfile).exists())
        # delete everything, import
        self.clean()
        self.cli(f'runtime import --path={expfile}')
        self.assertIn('reg', om.models.list())
        self.assertIn('sample', om.datasets.list())
        # import and promote model (twice to get 2 versions)
        self.clean()
        self.cli(f'runtime import --promote --path={expfile} models/*')
        self.cli(f'runtime import --promote --path={expfile} models/*')
        self.assertEqual(len(om.models.revisions('reg')), 2)

    def test_cli_deploy_steps(self):
        om = self.om
        self.make_model('reg')
        self.make_dataset_from_dataframe('sample')
        # write a deployfile
        deployfile = Path(om.defaults.OMEGA_TMP) / 'deployfile.yaml'
        with open(deployfile, 'w') as fout:
            steps = """
            runtime:
                - action: {action}
                  name: |
                     models/reg 
                     datasets/sample
            """
            fout.writelines(steps)
        # dry run
        self.cli(f'runtime deploy export --steps {deployfile} --dry')
        expected = self.pretend_log('DRY: om runtime  export models/reg datasets/sample')
        self.assertLogContains('info', expected)
        self.cli(f'runtime deploy import --steps {deployfile} --dry')
        expected = self.pretend_log('DRY: om runtime  import models/reg datasets/sample')
        self.assertLogContains('info', expected)
        # actually do it
        self.cli(f'runtime deploy export --steps {deployfile}')
        # delete everything, import
        self.clean()
        self.cli(f'runtime deploy import --steps {deployfile}')
        print(self.get_log('info'))
        self.assertIn('reg', om.models.list())
        self.assertIn('sample', om.datasets.list())
        # override action
        with open(deployfile, 'w') as fout:
            steps = """
                    runtime:
                        - action: foobar
                          name: test
                    """
            fout.writelines(steps)
        # dry run
        self.cli(f'runtime deploy export --steps {deployfile} --dry')
        expected = self.pretend_log('DRY: om runtime foobar test')


    def test_cli_restart_app(self):
        om = self.om
        om.runtime = MagicMock()
        om.runtime.auth.userid = 'testuser'
        om.runtime.auth.apikey = 'apikey'
        self.make_model('reg')
        # use the default REST API as the /apps url
        with patch('omegaml.client.cli.runtime.requests') as requests, \
             patch('omegaml.client.cli.runtime.get_omega') as get_omega:
            get_omega.return_value = om
            self.cli('runtime restart app apps/test')
            requests.get.assert_called()
            self.assertEqual(requests.get.call_args_list[0][0], ('local/apps/api/stop/testuser/test',))
            self.assertEqual(requests.get.call_args_list[1][0], ('local/apps/api/start/testuser/test',))
        # use a specific apphub URL
        with patch('omegaml.client.cli.runtime.requests') as requests, \
             patch('omegaml.client.cli.runtime.get_omega') as get_omega:
            get_omega.return_value = om
            self.cli('runtime restart app apps/test --apphub-url http://myapphub.com')
            requests.get.assert_called()
            self.assertEqual(requests.get.call_args_list[0][0], ('http://myapphub.com/apps/api/stop/testuser/test',))
            self.assertEqual(requests.get.call_args_list[1][0], ('http://myapphub.com/apps/api/start/testuser/test',))

