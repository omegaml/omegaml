import json
import unittest
from pathlib import Path
from unittest import TestCase

import warnings

from omegaml import Omega
from omegaml.tests.util import OmegaTestMixin
from omegaml.util import module_available

try:
    from omegaml.backends.mlflow.gitprojects import MLFlowGitProjectBackend
    from omegaml.backends.mlflow.localprojects import MLFlowProjectBackend, MLFlowProject
except:
    warnings.warn("mlflow not installed")
else:
    @unittest.skipUnless(module_available('mlflow'), 'mlflow not available')
    class TestMLFlowProjects(OmegaTestMixin, TestCase):
        def setUp(self):
            om = self.om = Omega()
            self.clean()
            om.models.register_backend(MLFlowProjectBackend.KIND, MLFlowProjectBackend)
            om.models.register_backend(MLFlowGitProjectBackend.KIND, MLFlowGitProjectBackend)

        def test_mlflow_project_local(self):
            import omegaml
            # store a local MLFlow project, use kind=mlflow.project
            project_path = Path(omegaml.__file__).parent / 'example' / 'mlflow' / 'project'
            om = self.om
            meta = om.scripts.put(str(project_path), 'myproject', kind='mlflow.project')
            self.assertEqual(meta.kind, MLFlowProjectBackend.KIND)
            # get it back
            mod = om.scripts.get('myproject')
            self.assertIsInstance(mod, MLFlowProject)
            # run it on omegaml runtime
            result = om.runtime.script('myproject').run(entry_point='main.py', conda=False).get()
            data = json.loads(result)
            self.assertIn('output', data['result'])
            self.assertIn('hello', data['result']['output']['stdout'])

        def test_mlflow_project_local_prefix(self):
            import omegaml
            # store a local MLFlow project, use mlflow:// prefix
            project_path = Path(omegaml.__file__).parent / 'example' / 'mlflow' / 'project'
            om = self.om
            meta = om.scripts.put('mlflow://' + str(project_path), 'myproject')
            self.assertEqual(meta.kind, MLFlowProjectBackend.KIND)
            # get it back
            mod = om.scripts.get('myproject')
            self.assertIsInstance(mod, MLFlowProject)
            # run it on omegaml runtime
            result = om.runtime.script('myproject').run(entry_point='main.py', conda=False).get()
            data = json.loads(result)
            self.assertIn('output', data['result'])
            self.assertIn('hello', data['result']['output']['stdout'])

        def test_mlflow_project_remote(self):
            # store a local MLFlow project
            project_path = 'https://github.com/mlflow/mlflow#examples/quickstart'
            om = self.om
            meta = om.scripts.put(str(project_path), 'myproject', kind='mlflow.gitproject')
            self.assertEqual(meta.kind, MLFlowGitProjectBackend.KIND)
            # get it back
            mod = om.scripts.get('myproject')
            self.assertIsInstance(mod, MLFlowProject)
            # run it on omegaml runtime
            result = om.runtime.script('myproject').run(entry_point='mlflow_tracking.py', conda=False).get()
            data = json.loads(result)
            self.assertIn('output', data['result'])
            self.assertIn('succeeded', data['result']['output']['stderr'])

        def test_mlflow_gitproject_remote(self):
            # store a local MLFlow project
            project_path = 'mlflow+git://github.com/mlflow/mlflow#examples/quickstart'
            om = self.om
            meta = om.scripts.put(str(project_path), 'myproject')
            self.assertEqual(meta.kind, MLFlowGitProjectBackend.KIND)
            # get it back
            mod = om.scripts.get('myproject')
            self.assertIsInstance(mod, MLFlowProject)
            # run it on omegaml runtime
            result = om.runtime.script('myproject').run(entry_point='mlflow_tracking.py', conda=False).get()
            data = json.loads(result)
            self.assertIn('output', data['result'])
            self.assertIn('succeeded', data['result']['output']['stderr'])

