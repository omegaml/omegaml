from __future__ import absolute_import

from datetime import timedelta
from unittest import TestCase

import gridfs
from nbformat import v4

from omegaml import Omega
from omegaml.documents import Metadata
from omegaml.notebook.jobs import JobSchedule
from omegaml.util import settings as omegaml_settings, settings


class JobTests(TestCase):

    def setUp(self):
        super().setUp()
        for omx in (self.om, self.om['bucket']):
            for fn in omx.jobs.list():
                omx.jobs.drop(fn)

    @property
    def om(self):
        om = Omega(defaults=settings(reload=True))
        return om

    @property
    def fs(self):
        om = self.om
        defaults = omegaml_settings()
        fs = om.jobs.get_fs(defaults.OMEGA_NOTEBOOK_COLLECTION)
        return fs

    def test_job_put_get(self):
        """
        test job put and get
        """
        om = self.om
        # create a notebook
        cells = []
        code = "print 'hello'"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put the notebook
        meta = om.jobs.put(notebook, 'testjob')
        self.assertEqual(meta.name, 'testjob.ipynb')
        # read it back and see what's in it
        notebook2 = om.jobs.get('testjob')
        self.assertDictEqual(notebook2, notebook)

    def test_job_list(self):
        """
        test job listing
        """
        fs = self.fs
        om = self.om
        # create a notebook
        cells = []
        code = "print 'hello'"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put the notebook
        meta = om.jobs.put(notebook, 'testjob')
        self.assertEqual(meta.name, 'testjob.ipynb')
        nb = v4.new_notebook(cells=cells)
        job_list = self.om.jobs.list()
        expected = 'testjob.ipynb'
        self.assertIn(expected, job_list)

    def test_job_list_bucket(self):
        """
        test job listing in buckets
        """
        om = self.om
        omb = self.om['bucket']
        # create a notebook
        cells = []
        code = "print 'hello'"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put the notebook
        meta = om.jobs.put(notebook, 'testjob')
        self.assertEqual(meta.name, 'testjob.ipynb')
        nb = v4.new_notebook(cells=cells)
        job_list = self.om.jobs.list()
        expected = 'testjob.ipynb'
        # ensure only in default bucket
        self.assertIn(expected, job_list)
        self.assertNotIn(expected, omb.jobs.list())
        # put to new bucket
        omb.jobs.put(notebook, 'testjob')
        self.assertIn(expected, omb.jobs.list())


    def test_run_job_valid(self):
        """
        test running a valid job
        """
        om = self.om
        # create a notebook
        cells = []
        code = "print('hello')"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put the notebook
        meta = om.jobs.put(notebook, 'testjob')
        self.assertEqual(meta.name, 'testjob.ipynb')
        meta_job = om.jobs.run('testjob')
        self.assertIsInstance(meta_job, Metadata)
        meta = om.jobs.put(notebook, 'testjob')
        self.assertIn('job_results', meta.attributes)
        self.assertIn('job_runs', meta.attributes)
        runs = meta.attributes['job_runs']
        results = meta.attributes['job_results']
        self.assertEqual(len(runs), 1)
        self.assertEqual(len(results), 1)
        resultnb = results[0]
        self.assertTrue(om.jobs.exists(resultnb))
        self.assertEqual(runs[0]['results'], resultnb)

    def test_run_job_timeout(self):
        """
        test running a job that times out
        """
        om = self.om
        # create a long-running notebook
        cells = []
        code = "import time; time.sleep(15)"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        meta = om.jobs.put(notebook, 'testjob')
        # -- execute with default timeout, expect to succeed
        meta_job = om.jobs.run('testjob')
        self.assertIsInstance(meta_job, Metadata)
        meta = om.jobs.metadata('testjob')
        runs = meta.attributes['job_runs']
        results = meta.attributes['job_results']
        self.assertIn('job_runs', meta.attributes)
        self.assertEqual(len(results), 1)
        resultnb = results[0]
        self.assertTrue(om.jobs.exists(resultnb))
        self.assertEqual(runs[0]['results'], resultnb)
        # -- put the notebook with a timeout less than expected running time
        # -- expect run to fail due to timeout
        om.jobs.drop('testjob', force=True)
        meta = om.jobs.put(notebook, 'testjob')
        meta.kind_meta['ep_kwargs'] = dict(timeout=5)
        meta.save()
        self.assertEqual(meta.name, 'testjob.ipynb')
        meta_job = om.jobs.run('testjob')
        self.assertIsInstance(meta_job, Metadata)
        meta = om.jobs.metadata('testjob')
        self.assertIn('job_runs', meta.attributes)
        runs = meta.attributes['job_runs']
        this_run = runs[0]
        self.assertEqual(this_run['status'], 'ERROR')
        self.assertIn('execution timed out', this_run['message'])
        self.assertEqual(len(runs), 1)
        # -- retry with no timeout
        om.jobs.drop('testjob', force=True)
        meta = om.jobs.put(notebook, 'testjob')
        meta.kind_meta['ep_kwargs'] = dict(timeout=None)
        meta.save()
        meta_job = om.jobs.run('testjob')
        self.assertIsInstance(meta_job, Metadata)
        meta = om.jobs.metadata('testjob')
        runs = meta.attributes['job_runs']
        results = meta.attributes['job_results']
        self.assertIn('job_runs', meta.attributes)
        self.assertEqual(len(results), 1)
        resultnb = results[0]
        self.assertTrue(om.jobs.exists(resultnb))
        self.assertEqual(runs[0]['results'], resultnb)

    def test_run_job_invalid(self):
        """
        test running an invalid job
        """
        fs = self.fs
        om = self.om
        # create a notebook
        cells = []
        code = "INVALID PYTHON CODE"
        cells.append(v4.new_code_cell(source=code))
        notebook = v4.new_notebook(cells=cells)
        # put the notebook
        meta = om.jobs.put(notebook, 'testjob')
        self.assertEqual(meta.name, 'testjob.ipynb')
        nb = v4.new_notebook(cells=cells)
        meta_job = om.jobs.run('testjob')
        self.assertIsInstance(meta_job, Metadata)
        meta = om.jobs.put(notebook, 'testjob')
        runs = meta.attributes['job_runs']
        self.assertEqual(len(runs), 1)
        self.assertEqual('ERROR', runs[0]['status'])

    def test_run_nonexistent_job(self):
        om = self.om
        self.assertRaises(
            gridfs.errors.NoFile, om.jobs.run_notebook, 'dummys.ipynb')

    def test_scheduled_job_with_omegaml_block(self):
        om = self.om
        cells = []
        conf = """
        # omega-ml:
        #   run-at: "*/5 * * * *"
        """.strip()
        cmd = "print('hello')"
        cells.append(v4.new_code_cell(source=conf))
        cells.append(v4.new_code_cell(source=cmd))
        notebook = v4.new_notebook(cells=cells)
        # check we have a valid configuration object
        meta = om.jobs.put(notebook, 'testjob')
        self._check_scheduled_job()

    def test_scheduled_job_with_run_at_schedule(self):
        om = self.om
        cells = []
        conf = """
        # run-at: "*/5 * * * *"
        """.strip()
        cmd = "print('hello')"
        cells.append(v4.new_code_cell(source=conf))
        cells.append(v4.new_code_cell(source=cmd))
        notebook = v4.new_notebook(cells=cells)
        # check we have a valid configuration object
        meta = om.jobs.put(notebook, 'testjob')
        self._check_scheduled_job()

    def test_scheduled_job_with_cron_schedule(self):
        om = self.om
        cells = []
        conf = """
        # run-at: "*/5 * * * *"
        """.strip()
        cmd = "print('hello')"
        cells.append(v4.new_code_cell(source=conf))
        cells.append(v4.new_code_cell(source=cmd))
        notebook = v4.new_notebook(cells=cells)
        # check we have a valid configuration object
        meta = om.jobs.put(notebook, 'testjob')
        self._check_scheduled_job()

    def test_scheduled_job_with_nlp_schedule(self):
        om = self.om
        cells = []
        conf = """
        # schedule: daily, at 06:00
        """.strip()
        cmd = "print('hello')"
        cells.append(v4.new_code_cell(source=conf))
        cells.append(v4.new_code_cell(source=cmd))
        notebook = v4.new_notebook(cells=cells)
        om.jobs.put(notebook, 'testjob')
        self._check_scheduled_job()

    def test_scheduled_not_duplicated(self):
        om = self.om
        cells = []
        conf = """
                # schedule: daily, at 06:00
                """.strip()
        cmd = "print('hello')"
        cells.append(v4.new_code_cell(source=conf))
        cells.append(v4.new_code_cell(source=cmd))
        notebook = v4.new_notebook(cells=cells)
        om.jobs.put(notebook, 'testjob')
        self._check_scheduled_job(autorun=False, reschedule=False)
        meta = om.jobs.metadata('testjob')
        trigger = meta.attributes['triggers']
        self.assertEqual(len(trigger), 1)

    def test_scheduled_results_not_rescheduled(self):
        om = self.om
        cells = []
        conf = """
                        # schedule: daily, at 06:00
                        """.strip()
        cmd = "print('hello')"
        cells.append(v4.new_code_cell(source=conf))
        cells.append(v4.new_code_cell(source=cmd))
        notebook = v4.new_notebook(cells=cells)
        om.jobs.put(notebook, 'testjob')
        self._check_scheduled_job(autorun=True, reschedule=False)
        meta = om.jobs.metadata('testjob')
        runs = meta.attributes['job_runs']
        result_name = runs[-1]['results']
        meta_result = om.jobs.metadata(result_name)
        self.assertNotIn('triggers', meta_result.attributes)

    def _check_scheduled_job(self, autorun=True, reschedule=False):
        om = self.om
        meta = om.jobs.metadata('testjob')
        config = om.jobs.get_notebook_config('testjob')
        self.assertIn('run-at', config)
        self.assertIn('config', meta.attributes)
        self.assertIn('run-at', meta.attributes['config'])
        # check the job was scheduled
        self.assertIn('triggers', meta.attributes)
        trigger = meta.attributes['triggers'][-1]
        self.assertEqual(trigger['status'], 'PENDING')

        # run it as scheduled, check it is ok
        def get_trigger(event=None):
            # get last trigger or specified by event
            meta = om.jobs.metadata('testjob')
            triggers = meta.attributes['triggers']
            if not event:
                trigger = triggers[-1]
            else:
                trigger = [t for t in triggers if t['event'] == event][0]
            return trigger

        def assert_pending(event=None):
            trigger = get_trigger(event)
            self.assertEqual(trigger['status'], 'PENDING')

        def assert_ok(event=None):
            trigger = get_trigger(event)
            self.assertEqual(trigger['status'], 'OK')

        assert_pending()
        if autorun:
            # -- run by the periodic task. note we pass now= as to simulate a time
            kwargs = dict(now=trigger['run-at'])
            om.runtime.task('omegaml.notebook.tasks.execute_scripts').apply_async(kwargs=kwargs).get()
            assert_ok(event=trigger['event'])
            # -- it should be pending again
            assert_pending()
            # execute the scheduled job by event name
            trigger = get_trigger()
            om.runtime.job('testjob').run(event=trigger['event'])
            # the last run should be ok, and there should not be a new pending event
            # since we did not reschedule
            assert_ok()
            with self.assertRaises(AssertionError):
                assert_pending()
        if reschedule:
            # reschedule explicit and check we have a pending event
            next_time = trigger['run-at'] + timedelta(minutes=2)
            om.runtime.job('testjob').schedule(run_at='daily, at 07:00').get()
            assert_pending()

    def test_schedule_triggers_by_api(self):
        om = self.om
        cells = []
        cmd = "print('hello')"
        cells.append(v4.new_code_cell(source=cmd))
        notebook = v4.new_notebook(cells=cells)
        # check we have a valid configuration object
        om.jobs.put(notebook, 'testjob')
        schedule = om.jobs.Schedule(weekday='mon-fri', at='06:00')
        om.jobs.schedule('testjob', run_at=schedule)

    def test_jobschedule_maker(self):
        # basics
        sched = JobSchedule(minute='*')
        self.assertEqual(sched.text, 'Every minute')
        sched2 = JobSchedule.from_cron(sched.cron)
        self.assertEqual(sched2.text, 'Every minute')
        # day specs
        sched = JobSchedule(weekday='mon-fri', at='06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, Monday through Friday')
        self.assertEqual(sched.cron, '00 06 * * mon-fri')
        sched2 = JobSchedule.from_cron(sched.cron)
        self.assertEqual(sched2.text, sched.text)
        # day specs 2
        sched = JobSchedule(weekday='Mon-Fri', at='06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, Monday through Friday')
        self.assertEqual(sched.cron, '00 06 * * mon-fri')
        sched2 = JobSchedule.from_cron(sched.cron)
        self.assertEqual(sched2.text, sched.text)
        # day specs 3
        sched = JobSchedule(weekday='Mon-FRI', at='06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, Monday through Friday')
        self.assertEqual(sched.cron, '00 06 * * mon-fri')
        sched2 = JobSchedule.from_cron(sched.cron)
        self.assertEqual(sched2.text, sched.text)
        # day specs 4
        sched = JobSchedule(weekday='Mon-FRI', at='06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, Monday through Friday')
        self.assertEqual(sched.cron, '00 06 * * mon-fri')
        sched2 = JobSchedule.from_cron(sched.cron)
        self.assertEqual(sched2.text, sched.text)
        # multiple times
        sched = JobSchedule(weekday='mon-fri', at='06:05,12:05')
        self.assertEqual(sched.text, 'At 06:05 AM and 12:05 PM, Monday through Friday')
        self.assertEqual(sched.cron, '05 06,12 * * mon-fri')
        sched2 = JobSchedule.from_cron(sched.cron)
        self.assertEqual(sched2.text, sched.text)
        # months and days with every
        sched = JobSchedule(month='every 2', at='08:00', weekday='every 3')
        self.assertEqual(sched.text, 'At 08:00 AM, every 3 days of the week, every 2 months')
        self.assertEqual(sched.cron, '00 08 * */2 */3')
        sched2 = JobSchedule.from_cron(sched.cron)
        self.assertEqual(sched2.text, sched.text)
        # step days
        sched = JobSchedule(weekday='every 2nd', at='06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, every 2 days of the week')
        self.assertEqual(sched.cron, '00 06 * * */2')
        sched = JobSchedule(weekday='every 1st', at='06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, only on Monday')
        sched2 = JobSchedule.from_cron(sched.cron)
        self.assertEqual(sched2.text, sched.text)
        sched = JobSchedule(weekday='every 3rd', at='06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, every 3 days of the week')
        sched2 = JobSchedule.from_cron(sched.cron)
        self.assertEqual(sched2.text, sched.text)
        sched = JobSchedule(weekday='every 4th', at='06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, every 4 days of the week')
        sched2 = JobSchedule.from_cron(sched.cron)
        self.assertEqual(sched2.text, sched.text)
        # step hours
        sched = JobSchedule(hour='every 2nd', minute=0, weekday='mon-fri')
        self.assertEqual(sched.text, 'Every 2 hours, Monday through Friday')
        sched2 = JobSchedule.from_cron(sched.cron)
        self.assertEqual(sched2.text, sched.text)
        # step minutes
        sched = JobSchedule(minute='every 5', weekday='mon-fri')
        self.assertEqual(sched.text, 'Every 5 minutes, Monday through Friday')
        sched2 = JobSchedule.from_cron(sched.cron)
        self.assertEqual(sched2.text, sched.text)
        # text specs
        sched = JobSchedule('friday, at 06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, only on Friday')
        sched = JobSchedule('fridays, at 06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, only on Friday')
        sched = JobSchedule('Mondays and Fridays, at 06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, only on Monday and Friday')
        sched = JobSchedule('Mondays/Fridays, at 06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, only on Monday and Friday')
        sched = JobSchedule('monday-friday, at 06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, Monday through Friday')
        sched = JobSchedule('mon-fri, at 06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, Monday through Friday')
        sched = JobSchedule('mon-fri at 06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, Monday through Friday')
        sched = JobSchedule('Mon-Fri, at 06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, Monday through Friday')
        sched = JobSchedule('Mon-Fri, 06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, Monday through Friday')
        sched = JobSchedule('Mon-Fri 06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, Monday through Friday')
        sched = JobSchedule('at 06:00, Mon-Fri')
        self.assertEqual(sched.text, 'At 06:00 AM, Monday through Friday')
        sched = JobSchedule('monday-friday, 06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, Monday through Friday')
        sched = JobSchedule('every 2nd month, monday-friday, at 06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, Monday through Friday, every 2 months')
        sched = JobSchedule('every 5 minutes, every day, hour 6')
        self.assertEqual(sched.text, 'Every 5 minutes, at 06:00 AM')
        sched = JobSchedule('every 5 minutes every working day hour 6')
        self.assertEqual(sched.text, 'Every 5 minutes, at 06:00 AM, Monday through Friday')
        sched = JobSchedule('every 5 minutes every working day, hour 6')
        self.assertEqual(sched.text, 'Every 5 minutes, at 06:00 AM, Monday through Friday')
        sched = JobSchedule('every 5 minutes, every working day, hour 6')
        self.assertEqual(sched.text, 'Every 5 minutes, at 06:00 AM, Monday through Friday')
        sched = JobSchedule('every 5 minutes, on workdays, hours 6/7')
        self.assertEqual(sched.text, 'Every 5 minutes, at 06:00 AM and 07:00 AM, Monday through Friday')
        sched = JobSchedule('every 5 minutes, on workdays, in april')
        self.assertEqual(sched.text, 'Every 5 minutes, Monday through Friday, only in April')
        sched = JobSchedule('every 5 minutes, on weekends, in april')
        self.assertEqual(sched.text, 'Every 5 minutes, Saturday through Sunday, only in April')
        sched = JobSchedule('every 5 minutes, from monday to friday, in april')
        self.assertEqual(sched.text, 'Every 5 minutes, Monday through Friday, only in April')
        sched = JobSchedule('at 5 minutes, every hour, monday to friday, april')
        self.assertEqual(sched.text, 'At 5 minutes past the hour, Monday through Friday, only in April')
        sched = JobSchedule('1st day of month, at 06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, on day 1 of the month')
        sched = JobSchedule('mon-fri, 06:00')
        self.assertEqual(sched.text, 'At 06:00 AM, Monday through Friday')
        sched = JobSchedule('every 2nd hour, 5 minute, weekdays')
        self.assertEqual(sched.text, 'At 5 minutes past the hour, every 2 hours, Monday through Friday')
        sched = JobSchedule('every 5 minutes, from monday to friday, in april')
        self.assertEqual(sched.text, 'Every 5 minutes, Monday through Friday, only in April')
        sched = JobSchedule('every 4 hours, at 0 minutes, Monday through Friday')
        self.assertEqual(sched.text, 'Every 4 hours, Monday through Friday')
