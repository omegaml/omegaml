import os
import pandas as pd
import sys
import unittest
from pandas._testing import assert_frame_equal
from pathlib import Path
from sklearn.linear_model import LinearRegression
from types import ModuleType
from unittest.mock import patch

from omegaml import Omega
from omegaml.mixins.store.imexport import ObjectImportExportMixin, OmegaExportArchive, OmegaExporter
from omegaml.tests.util import OmegaTestMixin


class ImportExportMixinTests(OmegaTestMixin, unittest.TestCase):
    def setUp(self):
        self.om = om = Omega()
        self.om_restore = self.om['restore']
        for omx in (self.om, self.om_restore):
            self._apply_store_mixin(omx)
        self.clean()
        self.clean(bucket='restore')
        with OmegaExportArchive('/tmp/test', None) as arc:
            arc.clear()

    def _apply_store_mixin(self, omx):
        for store in (omx.datasets, omx.models, omx.jobs.store, omx.scripts, omx.streams):
            store.register_mixin(ObjectImportExportMixin)

    def test_dataframe_export(self):
        om = self.om
        # export
        df = pd.DataFrame({'x': range(10)})
        om.datasets.put(df, 'mydf', append=False)
        om.datasets.to_archive('mydf', '/tmp/test')
        # import
        om.datasets.drop('mydf', force=True)
        om.datasets.from_archive('/tmp/test', 'mydf')
        xdf = om.datasets.get('mydf')
        assert_frame_equal(xdf, df)

    def test_model_export_singleversion(self):
        om = self.om
        om_restore = self.om_restore
        model = LinearRegression()
        model.coef_ = 1
        om.models.put(model, 'mymodel')
        om.models.to_archive('mymodel', '/tmp/test')
        om.models.drop('mymodel', force=True)
        om.models.from_archive('/tmp/test', 'mymodel')
        mdl = om.models.get('mymodel')
        self.assertIsInstance(mdl, LinearRegression)
        om_restore.models.from_archive('/tmp/test', 'mymodel')
        mdl = om_restore.models.get('mymodel')
        self.assertIsInstance(mdl, LinearRegression)
        self.assertEqual(mdl.coef_, 1)

    def test_model_export_multiversion(self):
        om = self.om
        om_restore = self.om_restore
        model = LinearRegression()
        model.coef_ = 1
        model = LinearRegression()
        model.coef_ = 2
        om.models.put(model, 'mymodel', tag='latest')
        om.models.put(model, 'mymodel', tag='version2')
        om.models.to_archive('mymodel', '/tmp/test')
        om.models.drop('mymodel', force=True)
        om.models.from_archive('/tmp/test', 'mymodel')
        mdl = om.models.get('mymodel')
        self.assertIsInstance(mdl, LinearRegression)
        om_restore.models.from_archive('/tmp/test', 'mymodel')
        mdl = om_restore.models.get('mymodel')
        # we expect the latest version
        self.assertIsInstance(mdl, LinearRegression)
        self.assertEqual(mdl.coef_, 2)
        self.assertNotIn('versions', om_restore.models.metadata('mymodel').attributes)

    def test_model_multiple_versioned_export(self):
        om = self.om
        om_restore = self.om_restore
        model = LinearRegression()
        model.coef_ = 1
        om.models.put(model, 'mymodel', tag='version1')
        model.coef_ = 2
        om.models.put(model, 'mymodel', tag='version2')
        print(om.models.get('mymodel@version1').coef_)
        print(om.models.get('mymodel@version2').coef_)
        # save specific versions
        om.models.to_archive('mymodel@version1', '/tmp/test')
        om.models.to_archive('mymodel@version2', '/tmp/test')
        om.models.drop('mymodel', force=True)
        # restore specific versions
        om_restore.models.from_archive('/tmp/test', 'mymodel@version1')
        om_restore.models.from_archive('/tmp/test', 'mymodel@version2')
        # check we can access specific versions, as restored
        mdl = om_restore.models.get('mymodel@version1')
        self.assertIsInstance(mdl, LinearRegression)
        self.assertEqual(mdl.coef_, 1)
        mdl = om_restore.models.get('mymodel@version2')
        self.assertIsInstance(mdl, LinearRegression)
        self.assertEqual(mdl.coef_, 2)
        # we don't expect a versioned base model
        self.assertNotIn('mymodel', om.models.list())
        self.assertNotIn('mymodel@version1', om.models.list())
        self.assertNotIn('mymodel@version2', om.models.list())
        # promote from restore bucket into a versioned model
        om_restore.models.promote('mymodel@version1', om.models)
        om_restore.models.promote('mymodel@version2', om.models)
        # check the model is actually versioned
        mdl = om.models.get('mymodel@latest')
        self.assertIsInstance(mdl, LinearRegression)
        self.assertEqual(mdl.coef_, 2)
        self.assertEqual(om.models.list(hidden=True), ['mymodel'])
        self.assertNotIn('mymodel@version1', om.models.list())
        self.assertNotIn('mymodel@version2', om.models.list())
        self.assertEqual(len(om.models.revisions('mymodel')), 2)
        # check we can access the versioned model
        mdl = om.models.get('mymodel@version1')
        self.assertIsInstance(mdl, LinearRegression)
        self.assertEqual(mdl.coef_, 1)
        mdl = om.models.get('mymodel@version2')
        self.assertIsInstance(mdl, LinearRegression)
        self.assertEqual(mdl.coef_, 2)

    def test_jobs_export(self):
        om = self.om
        code = "print('hello world')"
        om.jobs.create(code, 'mynb')
        om.jobs.to_archive('mynb', '/tmp/test')
        om.jobs.drop('mynb', force=True)
        om.jobs.from_archive('/tmp/test', 'mynb')
        job = om.jobs.get('mynb')
        print(job)

    def test_script_export(self):
        om = self.om
        basepath = os.path.join(os.path.dirname(sys.modules['omegaml'].__file__), 'example')
        pkgpath = os.path.abspath(os.path.join(basepath, 'demo', 'helloworld'))
        pkgsrc = 'pkg://{}'.format(pkgpath)
        om.scripts.put(pkgsrc, 'helloworld')
        om.scripts.to_archive('helloworld', '/tmp/test')
        om.scripts.drop('helloworld', force=True)
        om.scripts.from_archive('/tmp/test', 'helloworld')
        mod = om.scripts.get('helloworld')
        self.assertIsInstance(mod, ModuleType)
        self.assertTrue(hasattr(mod, 'run'))

    def test_streams_export(self):
        om = self.om
        stream = om.streams.get('mystream')
        meta = om.streams.metadata('mystream')
        meta.attributes['some_data'] = 'foo'
        meta.save()
        om.streams.to_archive('mystream', '/tmp/test')
        om.streams.drop('mystream', force=True)
        om.streams.from_archive('/tmp/test', 'mystream')
        meta = om.streams.metadata('mystream')
        self.assertEqual(meta.attributes.get('some_data'), 'foo')

    def test_compress(self):
        om = self.om
        om_restore = self.om_restore
        # export
        df = pd.DataFrame({'x': range(10)})
        om.datasets.put(df, 'mydf', append=False)
        arc = om.datasets.to_archive('mydf', '/tmp/test')
        # create an archive
        arcfile = arc.compress()
        # -- the archive path is deleted
        self.assertFalse(Path(arc.path).exists())
        # -- there is an timestamped archive file (tgz)
        self.assertTrue(Path(arcfile).is_file())
        self.assertTrue(Path(arcfile).name.endswith('.tgz'))
        # import from the tgz archive
        om_restore.datasets.drop('mydf', force=True)
        om_restore.datasets.from_archive(arcfile, 'mydf')
        xdf = om_restore.datasets.get('mydf')
        assert_frame_equal(xdf, df)

    def test_runtime_exporter_export_import(self):
        om = self.om
        om_restore = self.om_restore
        df = pd.DataFrame({'x': range(10)})
        om.datasets.put(df, 'mydf', append=False)
        OmegaExporter(om).to_archive('/tmp/test', ['data/mydf'])
        imported = OmegaExporter(om_restore).from_archive('/tmp/test')
        meta = om_restore.datasets.metadata('mydf')
        self.assertIn('mydf', om_restore.datasets.list())
        self.assertEqual(imported, [meta])

    def test_runtime_exporter_export_import_compressed(self):
        om = self.om
        om_restore = self.om_restore
        df = pd.DataFrame({'x': range(10)})
        om.datasets.put(df, 'mydf', append=False)
        arcfile = OmegaExporter(om).to_archive('/tmp/test', ['data/mydf'], compress=True)
        with self.assertRaises(FileNotFoundError):
            OmegaExporter(om_restore).from_archive('/tmp/test')
        imported = OmegaExporter(om_restore).from_archive(arcfile)
        meta = om_restore.datasets.metadata('mydf')
        self.assertIn('mydf', om_restore.datasets.list())
        self.assertEqual(imported, [meta])

    def test_runtime_exporter_export_promote(self):
        om = self.om
        om_restore = self.om_restore
        # dataset
        df = pd.DataFrame({'x': range(10)})
        om.datasets.put(df, 'mydf', append=False)
        # models
        model = LinearRegression()
        model.coef_ = 1
        om.models.put(model, 'mymodel', tag='version1')
        model.coef_ = 2
        om.models.put(model, 'mymodel', tag='version2')
        # job
        code = "print('hello')"
        om.jobs.create(code, 'myjob')
        # export
        OmegaExporter(om).to_archive('/tmp/test', ['data/mydf',
                                                   'models/mymodel@version1',
                                                   'models/mymodel@version2',
                                                   'jobs/myjob'])
        # import
        # -- mock temp bucket retrieval in order to test promotion
        temp_bucket = om[OmegaExporter._temp_bucket]
        self._apply_store_mixin(temp_bucket)
        with patch.object(om_restore, '_get_bucket') as meth:
            meth.return_value = temp_bucket
            OmegaExporter(om_restore).from_archive('/tmp/test',
                                                   pattern='data/.*|models/.*',
                                                   promote_to=om_restore)
            self.assertIn('mydf', om_restore.datasets.list())
            self.assertIn('mymodel', om_restore.models.list())
            self.assertEqual(len(om_restore.models.revisions('mymodel')), 2)
            # check model versions are as expected
            # -- latest
            mdl = om_restore.models.get('mymodel')
            self.assertIsInstance(mdl, LinearRegression)
            self.assertEqual(mdl.coef_, 2)
            # previous
            mdlv1 = om_restore.models.get('mymodel@version1')
            self.assertIsInstance(mdlv1, LinearRegression)
            self.assertEqual(mdlv1.coef_, 1)
            # check jobs were not restored yet
            self.assertEqual(om_restore.jobs.list(), [])
            # restore jobs explicitly
            # -- note jobs promotion is not supported (pending #218)
            OmegaExporter(om_restore).from_archive('/tmp/test',
                                                   pattern='jobs/.*')
            self.assertEqual(om_restore.jobs.list(), ['myjob.ipynb'])
            # ensure models were not touched
            self.assertEqual(len(om_restore.models.revisions('mymodel')), 2)


if __name__ == '__main__':
    unittest.main()
