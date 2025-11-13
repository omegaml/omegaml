from pathlib import Path
from unittest import TestCase, skipUnless, skip

import os
import shutil
import unittest
from shutil import rmtree
from sklearn.linear_model import LinearRegression, LogisticRegression

from omegaml import Omega
from omegaml.backends.repository.ocireg import OCIRegistryBackend
from omegaml.backends.repository.orasreg import OrasOciRegistry
from omegaml.mixins.store.repository import RepositoryStorageMixin
from omegaml.tests.util import OmegaTestMixin


@skipUnless(shutil.which('oras') is not None, "oras executable cannot be found on PATH")
class TestOCIRegistryBackend(OmegaTestMixin, TestCase):
    """ """

    def setUp(self):
        self.om = om = Omega()
        om.models.register_backend(OCIRegistryBackend.KIND, OCIRegistryBackend)
        om.models.register_mixin(RepositoryStorageMixin)
        self.clean()

    def test_putget_bare(self):
        om = self.om
        # -- registry with no image specified
        meta = om.models.put('oci://ghcr.io', 'ocireg')
        self.assertIn('url', meta.kind_meta)
        self.assertEqual(meta.kind_meta, {'url': 'oci://ghcr.io'})
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.repo, None)
        self.assertEqual(reg.url, 'oci://ghcr.io')
        # -- requires specification of image on .get()
        reg = om.models.get('ocireg', image='namespace/myimage')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.url, 'oci://ghcr.io')
        self.assertEqual(reg.repo, 'namespace/myimage')
        # -- registry with namespace, but no image
        meta = om.models.put('oci://ghcr.io/namespace', 'ocireg', replace=True)
        self.assertEqual(meta.kind_meta, {'url': 'oci://ghcr.io/namespace'})
        reg = om.models.get('ocireg', image='myimage:latest')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.url, 'oci://ghcr.io/namespace')
        self.assertEqual(reg.repo, 'myimage:latest')

    def test_putget_bare_multilevel(self):
        om = self.om
        # -- registry with no image specified
        om.models.put('oci://ghcr.io', 'ocireg')
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.repo, None)
        self.assertEqual(reg.url, 'oci://ghcr.io')
        # -- requires specification of image on .get()
        reg = om.models.get('ocireg', image='namespace/foo/bar/myimage')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.repo, 'namespace/foo/bar/myimage')
        self.assertEqual(reg.url, 'oci://ghcr.io')
        # -- registry with namespace, but no image
        meta = om.models.put('oci://ghcr.io/namespace', 'ocireg', replace=True)
        self.assertEqual(meta.kind_meta['url'], 'oci://ghcr.io/namespace')
        reg = om.models.get('ocireg', image='foo/bar/myimage:latest')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.url, 'oci://ghcr.io/namespace')
        self.assertEqual(reg.repo, 'foo/bar/myimage:latest')

    def test_putget_namespaced(self):
        om = self.om
        # -- without image
        om.models.put('oci://ghcr.io/miraculixx', 'ocireg')
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.url, 'oci://ghcr.io/miraculixx')
        self.assertEqual(reg.repo, None)
        # -- specify image on load
        reg = om.models.get('ocireg', image='myimage:latest')
        self.assertEqual(reg.url, 'oci://ghcr.io/miraculixx')
        self.assertEqual(reg.repo, 'myimage:latest')
        # -- with image
        om.models.put('oci://ghcr.io/miraculixx/myimage', 'ocireg', replace=True)
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.url, 'oci://ghcr.io/miraculixx')
        self.assertEqual(reg.repo, 'myimage:latest')

    def test_putget_namespaced_multilevel(self):
        om = self.om
        # -- without image
        om.models.put('oci://ghcr.io/miraculixx', 'ocireg')
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.url, 'oci://ghcr.io/miraculixx')
        self.assertEqual(reg.repo, None)
        # -- specify image on load
        reg = om.models.get('ocireg', image='foo/bar/myimage:latest')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.url, 'oci://ghcr.io/miraculixx')
        self.assertEqual(reg.repo, 'foo/bar/myimage:latest')
        # -- with image
        om.models.put('oci://ghcr.io/miraculixx/foo/bar/myimage', 'ocireg', replace=True)
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.url, 'oci://ghcr.io/miraculixx')
        self.assertEqual(reg.repo, 'foo/bar/myimage:latest')

    def test_putget_port(self):
        om = self.om
        om.models.put('oci://ghcr.io:5000/miraculixx', 'ocireg')
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(reg.url, 'oci://ghcr.io:5000/miraculixx')

    def test_putget_ocidir_bar(self):
        om = self.om
        # -- no image
        om.models.put('ocidir:///tmp/registry', 'ocireg')
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(str(reg.url), 'ocidir:///tmp/registry')
        self.assertEqual(reg.repo, None)
        # -- image on get
        reg = om.models.get('ocireg', image='myimage:latest')
        self.assertEqual(str(reg.url), 'ocidir:///tmp/registry')
        self.assertEqual(reg.repo, 'myimage:latest')
        # -- with image
        om.models.put('ocidir:///tmp/registry/myimage:latest', 'ocireg', replace=True)
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(str(reg.url), 'ocidir:///tmp/registry')
        self.assertEqual(reg.repo, 'myimage:latest')
        # -- no image with a long registry path
        om.models.put('ocidir:///tmp/data/artifacts/registry', 'ocireg', replace=True)
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(str(reg.url), 'ocidir:///tmp/data/artifacts/registry')
        self.assertEqual(reg.repo, None)
        # -- image on get
        reg = om.models.get('ocireg', image='myimage:latest')
        self.assertEqual(str(reg.url), 'ocidir:///tmp/data/artifacts/registry')
        self.assertEqual(reg.repo, 'myimage:latest')

    def test_putget_ocidir_namespaced(self):
        om = self.om
        # -- no image
        om.models.put('ocidir:///tmp/registry/ns/namespace', 'ocireg')
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(str(reg.url), 'ocidir:///tmp/registry/ns/namespace')
        self.assertEqual(reg.repo, None)
        # -- image on get
        reg = om.models.get('ocireg', image='myimage:latest')
        self.assertEqual(str(reg.url), 'ocidir:///tmp/registry/ns/namespace')
        self.assertEqual(reg.repo, 'myimage:latest')
        # -- with image
        om.models.put('ocidir:///tmp/registry/ns/namespace/myimage:latest', 'ocireg', replace=True)
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(str(reg.url), 'ocidir:///tmp/registry/ns/namespace')
        self.assertEqual(reg.repo, 'myimage:latest')
        # -- no image with a long registry path
        om.models.put('ocidir:///tmp/data/artifacts/registry/ns/namespace', 'ocireg', replace=True)
        reg = om.models.get('ocireg')
        self.assertIsInstance(reg, OrasOciRegistry)
        self.assertEqual(str(reg.url), 'ocidir:///tmp/data/artifacts/registry/ns/namespace')
        self.assertEqual(reg.repo, None)
        # -- image on get
        reg = om.models.get('ocireg', image='myimage:latest')
        self.assertEqual(str(reg.url), 'ocidir:///tmp/data/artifacts/registry/ns/namespace')
        self.assertEqual(reg.repo, 'myimage:latest')

    def test_putget_model(self):
        om = self.om
        # create an empty oci registry
        rmtree('/tmp/registry', ignore_errors=True)
        om.models.put('ocidir:///tmp/registry', 'ocireg')
        model = LinearRegression()
        meta = om.models.put(model, 'regmodel', repo='ocireg')
        # check gridfile is empty, model is stored in registry
        reg = om.models.get('ocireg')
        self.assertEqual(meta.gridfile.read(), None)
        self.assertEqual(len(reg.artifacts(repo='regmodel:latest')), 1)
        # check metadata
        self.assertIn('sync', meta.attributes)
        self.assertEqual(meta.attributes['sync']['repo'], 'ocireg/regmodel:latest')
        # get model back from oci registry
        model = om.models.get('regmodel')
        self.assertIsInstance(model, LinearRegression)

    @skip('shall be resolved by vllm support')
    def test_putget_directories(self):
        import omegaml
        om = self.om
        # create an empty oci registry
        rmtree('/tmp/registry', ignore_errors=True)
        om.models.put('ocidir:///tmp/registry', 'ocireg')
        # save a complete directory, zip up
        # -- expect to store a zip file
        basedir = Path(omegaml.__file__).parent / 'example' / 'demo'
        meta = om.models.put(basedir, 'myfile', repo='ocireg')
        repo = om.models.get('ocireg')
        print(repo.artifacts('myfile:latest'))
        # get back
        extracted = om.models.get('myfile')
        self.assertTrue(extracted.is_dir())
        self.assertTrue((extracted / 'demo').is_dir())

    @skip("TODO not currently supported")
    def test_putget_multimodels(self):
        om = self.om
        # create an empty oci registry
        rmtree('/tmp/registry', ignore_errors=True)
        om.models.put('ocidir:///tmp/registry', 'ocireg')
        model1 = LinearRegression()
        model2 = LogisticRegression()
        # wrong mental model: a repository is a collection of layers, where each layer contains multiple files
        # OR each layer is one file/artifact.
        # .put(..., repo='myimage') => creates a ONE layer image/tag
        # store models and ensure gridfile is not used
        for (model, name) in zip((model1, model2), ('linreg', 'logreg')):
            meta = om.models.put(model, name, repo='ocireg/myimage')
            self.assertEqual(meta.gridfile.read(), None)
        reg = om.models.get('ocireg')
        self.assertEqual(len(reg.artifacts('myimage:latest')), 2)

    def test_resolve_uri_placeholders(self):
        om = self.om
        os.environ.update(
            OMEGA_GHCR_USERID='myuser',
            OMEGA_GHCR_APIKEY='myapikey',
        )
        om.models.put('oci://{OMEGA_GHCR_USERID}:{OMEGA_GHCR_APIKEY}@ghcr.io', 'ocireg')
        reg = om.models.get('ocireg')
        self.assertEqual(reg.url, 'oci://ghcr.io')
        self.assertEqual(reg.auth, ('myuser', 'myapikey'))

    def test_putget_model_versions(self):
        om = self.om
        # create an empty oci registry
        rmtree('/tmp/registry', ignore_errors=True)
        om.models.put('ocidir:///tmp/registry', 'ocireg')
        model = LinearRegression()
        meta1 = om.models.put(model, 'regmodel', repo='ocireg')
        meta2 = om.models.put(model, 'regmodel', repo='ocireg')
        # check gridfile is empty, model is stored in registry
        reg = om.models.get('ocireg')
        self.assertEqual(meta1.gridfile.read(), None)
        self.assertEqual(len(reg.artifacts(repo='regmodel:latest')), 1)
        # check metadata
        self.assertIn('sync', meta1.attributes)
        self.assertEqual(meta2.attributes['sync']['repo'], 'ocireg/regmodel:latest')
        # get model back from oci registry
        model = om.models.get('regmodel')
        self.assertIsInstance(model, LinearRegression)

    def test_transformer_repo(self):
        import torch
        from sentence_transformers import CrossEncoder
        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2", activation_fn=torch.nn.Sigmoid())

        from omegaml.backends.virtualobj import virtualobj

        @virtualobj
        def transformers(obj=None, name=None, meta=None, method=None, store=None, uri=None, **kwargs):
            print("transformers helper", method, store, kwargs)

            if method == 'put':
                def serializer(store, model, filename, **kwargs):
                    print('serializer', kwargs)
                    model.save_pretrained(str(filename))

                # -- uri is for repo support
                # -- helper=False avoids recursion
                return store.put(obj, name, kind='python.model', serializer=serializer, uri=uri, helper=False)

            if method == 'get':
                def loader(store, infile, filename=None, **kwargs):
                    print('loader', infile, filename, kwargs)
                    from sentence_transformers import CrossEncoder
                    model = CrossEncoder(str(filename))
                    return model

                # -- helper=False avoids recursion
                return store.get(name, kind='python.model', loader=loader, helper=False)

        om = self.om
        om.models.put(transformers, 'helpers/transformers', replace=True)
        om.models.put('ocidir:///tmp/myrepo', 'myrepo', replace=True)
        # first time there is no meta for mymodel
        # 1. helper virtualobj gets called
        # 2. calls VirtualObjHelper.put()
        # 3. from within virtualobj calls RepositoryMixin.put() again
        # 4. there is no meta, and hence no repo => calls GenericModelBackend (due to model=python.model)
        meta = om.models.put(model, 'mymodel', helper='helpers/transformers', replace=True, repo='myrepo')
        self.assertEqual(meta.kind, 'python.model')
        model_ = om.models.get('mymodel')
        self.assertIsInstance(model_, CrossEncoder)
        # second time, there *is* a meta for mymodel
        # -- (replace does not get handled)
        # -- steps 1 to 3 are the same (correct)
        # -- step 4 since there is a meta, it will use the explicit backend of the object, not the mixin hierarchy
        #    => thus we have to drop the model first (FIXME replace=True should do the trick, but is not processed)
        #    => if we don't drop first, we'll end up with an endless recursion due to super().put() keeps ending up in helper
        om.models.drop('mymodel', force=True)
        meta = om.models.put(model, 'mymodel', helper='helpers/transformers', repo='myrepo')
        self.assertEqual(meta.kind, 'python.model')
        model_ = om.models.get('mymodel')
        self.assertIsInstance(model_, CrossEncoder)


if __name__ == '__main__':
    unittest.main()
