import os

import unittest

from omegaml import Omega
from omegaml.documents import Metadata
from omegaml.util import settings as omegaml_settings


class JobTasksTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        # ensure that sub tasks run in test mode
        os.environ['OMEGA_TEST_MODE'] = '1'
        # ensure that sub tasks don't use authenticated runtime
        os.environ['OMEGA_ALLOW_TASK_DEFAULT_AUTH'] = 'yes'

        for omx in (self.om, self.om['bucket']):
            for fn in omx.jobs.list():
                omx.jobs.drop(fn)

    @property
    def om(self):
        om = Omega(defaults=omegaml_settings(reload=True))
        return om

    @property
    def fs(self):
        om = self.om
        defaults = omegaml_settings()
        fs = om.jobs.get_fs(defaults.OMEGA_NOTEBOOK_COLLECTION)
        return fs

    def test_map(self):
        """ test runtime.job.map() works ok """
        om = self.om
        meta = om.jobs.create("print('hello')", 'main')
        job = om.runtime.job('main')
        tasks = job.map(range(2))
        self.assertEqual(len(tasks), 2)
        self.assertTrue(all(isinstance(t, Metadata) for t in tasks))
        status = job.status().set_index('name')
        for t in tasks:
            self.assertIn('task_id', t.attributes)
            task_name = t.attributes['job']['task_name']
            result = t.attributes['job_runs'][-1]
            self.assertEqual(result['status'], 'OK')
            self.assertEqual(status.loc[t.name, 'run_status'], 'OK')

    def test_map_fail(self):
        """ test runtime.job.map() works with erronous jobs """
        om = self.om
        # introduce some error
        meta = om.jobs.create("raise ValueError()", 'main')
        job = om.runtime.job('main')
        tasks = job.map(range(2))
        self.assertEqual(len(tasks), 2)
        self.assertTrue(all(isinstance(t, Metadata) for t in tasks))
        status = job.status().set_index('name')
        for t in tasks:
            self.assertIn('task_id', t.attributes)
            task_name = t.attributes['job']['task_name']
            result = t.attributes['job_runs'][-1]
            self.assertEqual(result['status'], 'ERROR')
            self.assertEqual(status.loc[t.name, 'run_status'], 'ERROR')
        # fix error and restart
        meta = om.jobs.create("print('hello')", 'main')
        tasks = job.restart(reset=True)
        self.assertEqual(len(tasks), 2)
        self.assertTrue(all(isinstance(t, Metadata) for t in tasks))
        status = job.status().set_index('name')
        for t in tasks:
            self.assertIn('task_id', t.attributes)
            task_name = t.attributes['job']['task_name']
            result = t.attributes['job_runs'][-1]
            self.assertEqual(result['status'], 'ERROR')
            self.assertEqual(status.loc[t.name, 'run_status'], 'ERROR')

    def test_map_groups(self):
        """ test runtime.job.map() works with multiple groups """
        import os

        om = self.om
        meta = om.jobs.create("print('hello')", 'main')
        job = om.runtime.job('main')

        def check(tasks):
            self.assertEqual(len(tasks), 2)
            self.assertTrue(all(isinstance(t, Metadata) for t in tasks))
            status = job.status().set_index('name')
            for t in tasks:
                self.assertIn('task_id', t.attributes)
                task_name = t.attributes['job']['task_name']
                result = t.attributes['job_runs'][-1]
                self.assertEqual(result['status'], 'OK')
                self.assertEqual(status.loc[t.name, 'run_status'], 'OK')
            return tasks

        group1_tasks = job.map(range(2))
        group2_tasks = job.map(range(2))
        check(group1_tasks)
        check(group2_tasks)

        all_groups = job.status('*')
        self.assertEqual(len(all_groups), 4)


if __name__ == '__main__':
    unittest.main()
