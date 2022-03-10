import unittest
from datetime import datetime

import pandas as pd
from pandas._testing import assert_frame_equal

from omegaml import Omega
from omegaml.mixins.store.datarevision import DataRevisionMixin
from omegaml.tests.util import OmegaTestMixin


class DataRevisionMixinTests(OmegaTestMixin, unittest.TestCase):
    def setUp(self):
        self.om = Omega()
        self.clean()
        self.om.datasets.register_mixin(DataRevisionMixin)

    def test_revision_store_retrieve(self):
        """ check storing revisions works as expected"""
        om = self.om
        # storing dataset by numeric index, 0-9
        df_a = pd.DataFrame({
            'x': range(0, 10)
        })
        meta = om.datasets.put(df_a, 'revtest', append=False, revisions=True)
        self.assertIn('revisions', meta.kind_meta)
        self.assertEqual(meta.kind_meta['revisions']['seq'], 0)
        # update idx data 0-5 with new data
        df_b = pd.DataFrame({
            'x': range(5, 10)
        })
        meta = om.datasets.put(df_b, 'revtest')
        self.assertEqual(meta.kind_meta['revisions']['seq'], 1)
        # check we retrieve updated frame as the latest revision
        dfx = om.datasets.get('revtest')
        assert_frame_equal(dfx.iloc[0:5], df_b.iloc[0:5])
        assert_frame_equal(dfx.iloc[5:], df_a.iloc[5:])
        # check we can get a specific version
        dfx = om.datasets.get('revtest', revision=0)
        assert_frame_equal(dfx, df_a)
        # check the data is clean from revision internals
        self.assertNotIn('_om#revision', dfx.columns)
        self.assertNotIn('_om#revision', df_a)
        self.assertNotIn('_delete_', dfx.columns)
        self.assertNotIn('_delete_', df_a)
        # check we can get a specific changeset
        dfx = om.datasets.get('revtest', changeset=1)
        assert_frame_equal(dfx, df_b)
        # check we can append new data and get back revisions with and without this
        df_c = pd.DataFrame({
            'x': range(11, 15)
        }, index=range(11, 15))
        meta = om.datasets.put(df_c, 'revtest')
        dfx = om.datasets.get('revtest', revision=-1)
        assert_frame_equal(dfx.iloc[5:10], df_a.iloc[5:10])
        assert_frame_equal(dfx.iloc[0:5], df_b.iloc[0:5])
        assert_frame_equal(dfx.iloc[10:], df_c.iloc[0:])
        # check we can update previously appended data
        df_d = pd.DataFrame({
            'x': range(16, 18)
        }, index=range(12, 14))
        meta = om.datasets.put(df_d, 'revtest')
        dfx = om.datasets.get('revtest', revision=-1)
        assert_frame_equal(dfx.iloc[5:10], df_a.iloc[5:10])
        assert_frame_equal(dfx.iloc[0:5], df_b.iloc[0:5])
        assert_frame_equal(dfx.iloc[10:11], df_c.iloc[0:1])
        assert_frame_equal(dfx.iloc[11:13], df_d.iloc[0:])
        assert_frame_equal(dfx.iloc[13:], df_c.iloc[3:])

    def test_revision_store_retrieve_multiple(self):
        om = self.om
        # storing dataset by numeric index, 0-9
        df_a = pd.DataFrame({
            'x': range(0, 10)
        }, index=range(0, 10))
        meta = om.datasets.put(df_a, 'revtest', append=False, revisions=True)
        # update with new data
        df_b = pd.DataFrame({
            'x': range(3, 6)
        }, index=range(3, 6))
        meta = om.datasets.put(df_b, 'revtest')
        # update with new data
        df_c = pd.DataFrame({
            'x': range(6, 10)
        }, index=range(6, 10))
        meta = om.datasets.put(df_c, 'revtest')
        # get back original revision
        dfx = om.datasets.get('revtest', revision=0)
        assert_frame_equal(dfx, df_a)
        # get back second revision
        dfx = om.datasets.get('revtest', revision=1)
        assert_frame_equal(dfx.iloc[0:3], df_a.iloc[0:3])
        assert_frame_equal(dfx.iloc[3:6], df_b.iloc[0:])
        assert_frame_equal(dfx.iloc[6:], df_a.iloc[6:])
        # get back most recent
        dfx = om.datasets.get('revtest', revision=2)
        assert_frame_equal(dfx.iloc[0:3], df_a.iloc[0:3])
        assert_frame_equal(dfx.iloc[3:6], df_b.iloc[0:])
        assert_frame_equal(dfx.iloc[6:], df_c.iloc[0:])

    def test_revisions_bydate(self):
        om = self.om
        # storing dataset by numeric index, 0-9
        df_a = pd.DataFrame({
            'x': range(0, 10)
        })
        dt_a = datetime.utcnow()
        meta = om.datasets.put(df_a, 'revtest', append=False, revisions=True, revision_dt=dt_a)
        # update idx data 0-5 with new data
        df_b = pd.DataFrame({
            'x': range(5, 10)
        })
        dt_b = datetime.utcnow()
        meta = om.datasets.put(df_b, 'revtest', revision_dt=dt_b)
        # get back original revision by date
        dfx = om.datasets.get('revtest', revision=dt_a)
        assert_frame_equal(dfx, df_a)
        # get back most recent by date
        dfx = om.datasets.get('revtest', revision=dt_b)
        assert_frame_equal(dfx.iloc[0:5], df_b.iloc[0:5])
        assert_frame_equal(dfx.iloc[5:], df_a.iloc[5:])
        # retrieve by string-specified date
        dfx = om.datasets.get('revtest', revision=dt_a.isoformat())
        assert_frame_equal(dfx, df_a)

    def test_revisions_bytag(self):
        om = self.om
        # storing dataset by numeric index, 0-9
        df_a = pd.DataFrame({
            'x': range(0, 10)
        })
        meta = om.datasets.put(df_a, 'revtest', append=False, revisions=True,
                               tag='rev_a')
        # get back original revision by atag
        dfx = om.datasets.get('revtest', revision='rev_a')
        assert_frame_equal(dfx, df_a)

    def test_revisions_bynegativeindex(self):
        om = self.om
        # storing dataset by numeric index, 0-9
        df_a = pd.DataFrame({
            'x': range(0, 10)
        }, index=range(0, 10))
        meta = om.datasets.put(df_a, 'revtest', append=False, revisions=True)
        # update with new data
        df_b = pd.DataFrame({
            'x': range(3, 6)
        }, index=range(3, 6))
        meta = om.datasets.put(df_b, 'revtest')
        # update with new data
        df_c = pd.DataFrame({
            'x': range(6, 10)
        }, index=range(6, 10))
        meta = om.datasets.put(df_c, 'revtest')
        # get back original revision
        # -- same as df_a
        dfx = om.datasets.get('revtest', revision=-3)
        assert_frame_equal(dfx, df_a)
        # get back second revision
        # -- parts of df_a and df_b
        dfx = om.datasets.get('revtest', revision=-2)
        assert_frame_equal(dfx.iloc[0:3], df_a.iloc[0:3])
        assert_frame_equal(dfx.iloc[3:6], df_b.iloc[0:])
        assert_frame_equal(dfx.iloc[6:], df_a.iloc[6:])
        # get back most recent
        # -- parts of df_a, df_b, df_c
        dfx = om.datasets.get('revtest', revision=-1)
        assert_frame_equal(dfx.iloc[0:3], df_a.iloc[0:3])
        assert_frame_equal(dfx.iloc[3:6], df_b.iloc[0:])
        assert_frame_equal(dfx.iloc[6:], df_c.iloc[0:])

    def test_revisions_list(self):
        om = self.om
        # storing dataset by numeric index, 0-9
        df_a = pd.DataFrame({
            'x': range(0, 10)
        })
        meta = om.datasets.put(df_a, 'revtest', append=False, revisions=True,
                               tag='rev_a')
        df_b = pd.DataFrame({
            'x': range(0, 2)
        })
        om.datasets.put(df_b, 'revtest')
        # check revisions list
        revs = om.datasets.revisions('revtest')
        self.assertEqual(len(revs), 2)
        self.assertEqual(['dt', 'seq', 'tags', 'delete'], list(revs.columns))

    def test_revisions_delete_byindex(self):
        om = self.om
        # storing dataset by numeric index, 0-9
        df_a = pd.DataFrame({
            'x': range(0, 10)
        })
        meta = om.datasets.put(df_a, 'revtest', append=False, revisions=True)
        df_b = pd.DataFrame({
            'x': range(5, 8),
        }, index=range(5, 8))
        # apply deletions
        df_b['_delete_'] = True
        meta = om.datasets.put(df_b, 'revtest', tag='with-deletions')
        # check deletion happened
        dfx = om.datasets.get('revtest')
        self.assertEqual(len(dfx), len(df_a) - len(df_b))
        assert_frame_equal(dfx.iloc[0:5], df_a.iloc[0:5])
        assert_frame_equal(dfx.iloc[5:], df_a.iloc[8:])
        # check deletions are applied on getting a revision
        df_c = pd.DataFrame({
            'x': range(5, 8),
        }, index=range(5, 8))
        # -- add the deleted rows again
        om.datasets.put(df_c, 'revtest')
        dfx = om.datasets.get('revtest', revision=-1)
        self.assertEqual(len(dfx), len(df_a))
        assert_frame_equal(dfx.sort_index()[['x']], df_a[['x']])
        # get back revisions before re-adding, i.e. revisions applied one by one
        dfx = om.datasets.get('revtest', revision='with-deletions')
        self.assertEqual(len(dfx), len(df_a) - len(df_b))
        assert_frame_equal(dfx.iloc[0:5], df_a.iloc[0:5])
        assert_frame_equal(dfx.iloc[5:], df_a.iloc[8:])

    def test_revisions_delete_byflag(self):
        om = self.om
        # storing dataset by numeric index, 0-9
        df_a = pd.DataFrame({
            'x': range(0, 10)
        })
        meta = om.datasets.put(df_a, 'revtest', append=False, revisions=True)
        df_b = pd.DataFrame({
            'x': range(5, 8),
        }, index=range(5, 8))
        # apply deletions
        meta = om.datasets.put(df_b, 'revtest', delete=True, tag='with-deletions')
        # check deletion happened
        dfx = om.datasets.get('revtest')
        self.assertEqual(len(dfx), len(df_a) - len(df_b))
        assert_frame_equal(dfx.iloc[0:5], df_a.iloc[0:5])
        assert_frame_equal(dfx.iloc[5:], df_a.iloc[8:])
        # check deletions are applied on getting a revision
        df_c = pd.DataFrame({
            'x': range(5, 8),
        }, index=range(5, 8))
        # -- add the deleted rows again
        om.datasets.put(df_c, 'revtest')
        dfx = om.datasets.get('revtest', revision=-1)
        self.assertEqual(len(dfx), len(df_a))
        assert_frame_equal(dfx.sort_index()[['x']], df_a[['x']])
        # get back revisions before re-adding, i.e. revisions applied one by one
        dfx = om.datasets.get('revtest', revision='with-deletions')
        self.assertEqual(len(dfx), len(df_a) - len(df_b))
        assert_frame_equal(dfx.iloc[0:5], df_a.iloc[0:5])
        assert_frame_equal(dfx.iloc[5:], df_a.iloc[8:])

    def test_revisions_trace(self):
        om = self.om
        # storing dataset by numeric index, 0-9
        df_a = pd.DataFrame({
            'x': range(0, 10)
        })
        meta = om.datasets.put(df_a, 'revtest', append=False, revisions=True,
                               tag='rev_a')
        # get back original revision by atag
        dfx = om.datasets.get('revtest', revision='rev_a', trace_revisions=True)
        assert_frame_equal(dfx[['x']], df_a)
        self.assertIn('_om#revision', dfx.columns)
        self.assertIn('_delete_', dfx.columns)

