"""Tests for GitHub issue #600 - unique execution constraint support in omegaml jobs.

This module verifies the ``unique`` parameter added to both 
:py:meth:`OmegaJobs.schedule` and :py:meth:`OmegaJobs.run_notebook` that ensures  
scheduled/run jobs only run at most once during a specified time window (e.g.,
once per day, once per month).
"""
import datetime
import unittest


class TestResolveUniqueKey(unittest.TestCase):
    """Test the resolve_unique_key function for issue #600."""

    def test_today_date_word(self):
        from omegaml.notebook.uniquejob import resolve_unique_key as r  
        expected = datetime.datetime.now().strftime('%Y-%m-%d')
        self.assertEqual(r('myjob', 'today'), expected)

    def test_yesterday_date_word(self):
        from omegaml.notebook.uniquejob import resolve_unique_key as r
        result = r('myjob', 'yesterday')
        self.assertIsInstance(result, str)

    def test_tomorrow_date_word(self):  
        from omegaml.notebook.uniquejob import resolve_unique_key as r
        # Should complete without raising exception
        self.assertIsInstance(r('myjob', 'tomorrow'), str)

    def test_strftime_yearly_pattern(self):  
        from omegaml.notebook.uniquejob import resolve_unique_key as r
        self.assertRegex(r('myjob', '%Y'), r"\\d{4}")

    def test_strftime_monthly_pattern(self): 
        from omegaml.notebook.uniquejob import resolve_unique_key as r
        # '%Y-%m' format should return something like '2026-01'
        self.assertRegex(r('myjob', '%Y-%m'), r"\\d{4}-\\d{2}")

    def test_strftime_weekly_pattern(self): 
        from omegaml.notebook.uniquejob import resolve_unique_key as r
        # '%Y-W%V' should return something like '2026-W03'
        resolved = r('myjob', '%Y-W%V')  
        result_str = str(resolved).replace('W', '-x')  # Temporarily swap for regex match
        self.assertRegex(result_str, r"\\d{4}-x\\d{2}")

    def test_invalid_date_word(self):
        from omegaml.notebook.uniquejob import resolve_unique_key as r
        with self.assertRaises(ValueError):  
            r('test_job', 'not_a_valid_date_word')


class TestJobUniqueKey(unittest.TestCase):
    """Test the JobUniqueKey class (issue #600)."""

    def test_handles_slash_paths(self):  
        from omegaml.notebook.uniquejob import JobUniqueKey as K
        key = K('path/to/name', 'today')
        self.assertNotIn('/', key.collection_name)  



if __name__ == '__main__':  
    # Run all tests  
    unittest.main(verbosity=2)
    
