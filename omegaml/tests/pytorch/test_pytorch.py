from unittest import TestCase, skipUnless

import dill

from omegaml.backends.genericmodel import GenericModelBackend
from omegaml.backends.pytorch import PytorchModelBackend
from omegaml.backends.virtualobj import virtualobj
from omegaml.tests.util import OmegaTestMixin
from omegaml.util import module_available

try:
    import torch
except:
    @skipUnless(module_available('torch'), "skipping due to pytorch is not installed")
    class TestPytorchModels(OmegaTestMixin, TestCase):
        pass
else:
    @skipUnless(module_available('torch'), "skipping due to pytorch is not installed")
    class TestPytorchModels(OmegaTestMixin, TestCase):
        def setUp(self):
            super().setUp()
            self.clean()
            om = self.om
            om.models.register_backend(GenericModelBackend.KIND, GenericModelBackend)
            om.models.register_backend(PytorchModelBackend.KIND, PytorchModelBackend)

        def test_pytorch_model_genericmodel(self):
            om = self.om
            # create, serialize and save the model as a generic model
            # -- note we use a custom serializer
            model = self._create_torch_model()
            serializer = lambda store, model, filename, **kwargs: torch.save(model, filename, pickle_module=dill)
            meta = om.models.put(model, 'torchmodel.pth', serializer=serializer, kind='python.model')
            self.assertEqual(meta.kind, GenericModelBackend.KIND)

            # create a virtual object for model loading and prediction
            @virtualobj
            def torchmodel(store=None, data=None, **kwargs):
                import dill
                import torch
                # -- note we use a custom loader
                loader = lambda store, infile, **kwargs: torch.load(infile, pickle_module=dill)
                model = store.get('torchmodel.pth', loader=loader)
                data = torch.tensor(data, dtype=torch.float)
                return model(data)

            # save the virtualobj
            om.models.put(torchmodel, 'torchmodel')
            # 1) test virtualobj
            # -- load the virtualobj and run a prediction
            vobj = om.models.get('torchmodel')
            data = torch.randn(5, 10)
            result = vobj(store=om.models, data=data.tolist())
            output = torch.tensor(result, dtype=torch.float)
            self.assertEqual(output.shape, torch.Size([5, 1]))
            # 2) test prediction via runtime
            data = torch.randn(5, 10)
            result = om.runtime.model('torchmodel').predict(data.tolist())
            output = torch.tensor(result.get(), dtype=torch.float)
            self.assertEqual(output.shape, torch.Size([5, 1]))

        def test_pytorch_model_virtualobj(self):
            om = self.om
            # createa, serialize and save the model
            model = self._create_torch_model()
            torch.save(model, '/tmp/torchmodel.pth', pickle_module=dill)
            om.models.put('/tmp/torchmodel.pth', 'torchmodel.pth')

            # create a virtual object for model loading and prediction
            @virtualobj
            def torchmodel(store=None, data=None, **kwargs):
                import dill
                import torch
                model = torch.load(store.get('torchmodel.pth'), pickle_module=dill)
                data = torch.tensor(data, dtype=torch.float)
                return model(data)

            # save the virtualobj
            om.models.put(torchmodel, 'torchmodel')
            # 1) test virtualobj
            # -- load the virtualobj and run a prediction
            vobj = om.models.get('torchmodel')
            data = torch.randn(5, 10)
            result = vobj(store=om.models, data=data.tolist())
            output = torch.tensor(result, dtype=torch.float)
            self.assertEqual(output.shape, torch.Size([5, 1]))
            # 2) test prediction via runtime
            data = torch.randn(5, 10)
            result = om.runtime.model('torchmodel').predict(data.tolist())
            output = torch.tensor(result.get(), dtype=torch.float)
            self.assertEqual(output.shape, torch.Size([5, 1]))

        def test_pytorch_model_helper(self):
            om = self.om
            model = self._create_torch_model()
            self._test_torch_model(model)

            # implement a dynamic backend that can handle torch models as a generic approach
            @virtualobj
            def torchhelper(method=None, obj=None, name=None, meta=None, store=None, data=None, **kwargs):
                import torch
                import dill
                from pathlib import Path
                # support (obj, virtualobj) syntax to save a virtualobj along with obj?
                # prepare paths
                fnpath = Path(store.tmppath) / f'saved_{name}.pth'
                fnpath.parent.mkdir(parents=True, exist_ok=True)
                # save model
                if method == 'put':
                    torch.save(obj, fnpath, pickle_module=dill)
                    meta = store.put(fnpath, name)
                    return meta
                # load model
                if method == 'get':
                    store.get(name, local=fnpath, helper=False)
                    model = torch.load(fnpath, pickle_module=dill)
                    return model
                # run prediction
                if method == 'predict':
                    X = torch.tensor(data, dtype=torch.float)
                    return obj(X).tolist()

            # save the helper as a dynamic backend that supports particular types of models
            om.models.put(torchhelper, 'torchhelper', supports='.*SimpleLinear.*')
            # save multiple models, note we can save the model directly from the instance
            om.models.put(model, 'torchmodel')
            om.models.put(model, 'torchmodel2')
            # load model, test it
            model = om.models.get('torchmodel')
            self._test_torch_model(model)
            # load second model
            model2 = om.models.get('torchmodel2')
            self._test_torch_model(model2)
            # check we have two different model instances
            self.assertFalse(model is model2)
            # test model via runtime
            for modelname in ('torchmodel', 'torchmodel2'):
                data = torch.randn(5, 10)
                result = om.runtime.model(modelname).predict(data.tolist())
                output = torch.tensor(result.get(), dtype=torch.float)
                self.assertEqual(output.shape, torch.Size([5, 1]))

            # check logging models in tracking and restore from tracking
            # FIXME if experiment is called the same as an object with a helper we get recursion
            with om.runtime.experiment('xtorchmodel') as exp:
                exp.log_artifact(model, 'foo')
            model = exp.restore_artifacts(name='foo', run=-1)[0]
            self._test_torch_model(model)

        def test_pytorch_model_remote_uri(self):
            om = self.om
            # createa, serialize and save the model
            model = self._create_torch_model()
            torch.save(model, '/tmp/torchmodel.pth', pickle_module=dill)
            om.models.put('/tmp/torchmodel.pth', 'torchmodel.pth', uri='/tmp/remote')

            # create a virtual object for model loading and prediction
            @virtualobj
            def torchmodel(store=None, data=None, **kwargs):
                import dill
                import torch
                model = torch.load(store.get('torchmodel.pth'), pickle_module=dill)
                data = torch.tensor(data, dtype=torch.float)
                return model(data)

            # save the virtualobj
            om.models.put(torchmodel, 'torchmodel')
            # 1) test virtualobj
            # -- load the virtualobj and run a prediction
            vobj = om.models.get('torchmodel')
            data = torch.randn(5, 10)
            result = vobj(store=om.models, data=data.tolist())
            output = torch.tensor(result, dtype=torch.float)
            self.assertEqual(output.shape, torch.Size([5, 1]))
            # 2) test prediction via runtime
            data = torch.randn(5, 10)
            result = om.runtime.model('torchmodel').predict(data.tolist())
            output = torch.tensor(result.get(), dtype=torch.float)
            self.assertEqual(output.shape, torch.Size([5, 1]))

        def test_pytorch_model_oci_repo(self):
            om = self.om
            # create, serialize and save the model
            # -- create the model, serialize using torch
            model = self._create_torch_model()
            torch.save(model, '/tmp/torchmodel.pth', pickle_module=dill)
            # -- register an oci registry, save model to repository
            om.models.put('ocidir:///tmp/registry', 'ocireg')
            om.models.put('/tmp/torchmodel.pth', 'torchmodel.pth', repo='ocireg/torchmodel:v1')
            smodel = om.models.get('torchmodel.pth')
            model = torch.load(smodel, pickle_module=dill)

            # create a virtual object for model loading and prediction
            @virtualobj
            def torchmodel(store=None, data=None, **kwargs):
                import dill
                import torch
                model = torch.load(store.get('torchmodel.pth'), pickle_module=dill)
                data = torch.tensor(data, dtype=torch.float)
                return model(data)

            # save the virtualobj
            om.models.put(torchmodel, 'torchmodel')
            # 1) test virtualobj
            # -- load the virtualobj and run a prediction
            vobj = om.models.get('torchmodel')
            data = torch.randn(5, 10)
            result = vobj(store=om.models, data=data.tolist())
            output = torch.tensor(result, dtype=torch.float)
            self.assertEqual(output.shape, torch.Size([5, 1]))
            # 2) test prediction via runtime
            data = torch.randn(5, 10)
            result = om.runtime.model('torchmodel').predict(data.tolist())
            output = torch.tensor(result.get(), dtype=torch.float)
            self.assertEqual(output.shape, torch.Size([5, 1]))

        def test_pytorch_model_implied_helper(self):
            import torch.nn as nn
            om = self.om

            # create a helper for model saving, loading and prediction
            @virtualobj
            def torchmodel(obj=None, name=None, method=None, meta=None, store=None, data=None, **kwargs):
                import dill
                import torch

                load = lambda: torch.load(store.get(name, helper=False), pickle_module=dill)

                if method == 'predict':
                    model = load()
                    data = torch.tensor(data, dtype=torch.float)
                    return model(data)
                if method == 'get':
                    model = load()
                    return model
                if method == 'put':
                    torch.save(obj, '/tmp/torchmodel.pth', pickle_module=dill)
                    meta = store.put('/tmp/torchmodel.pth', name, helper=False)
                    return meta

            # -- create the model, serialize using torch
            model = self._create_torch_model()
            om.models.put(model, 'torchmodel', helper=torchmodel)
            # see we can get it back, and it is a new object
            model_ = om.models.get('torchmodel')
            self.assertIsInstance(model_, nn.Module)
            self.assertFalse(model_.__class__ is model.__class__)
            # use it to predict
            data = torch.randn(5, 10)
            result = model_(data)
            output = torch.tensor(result, dtype=torch.float)
            self.assertEqual(output.shape, torch.Size([5, 1]))
            # 2) test prediction via runtime
            data = torch.randn(5, 10)
            result = om.runtime.model('torchmodel').predict(data.tolist())
            output = torch.tensor(result.get(), dtype=torch.float)
            self.assertEqual(output.shape, torch.Size([5, 1]))

        def test_pytorch_model_backend(self):
            om = self.om
            model = self._create_torch_model()
            om.models.put(model, 'torchmodel')
            model_ = om.models.get('torchmodel')
            data = torch.randn(5, 10)
            result = model_(data)
            output = torch.tensor(result, dtype=torch.float)
            self.assertEqual(output.shape, torch.Size([5, 1]))
            result = om.runtime.model('torchmodel').predict(data.tolist())
            output = torch.tensor(result.get(), dtype=torch.float)
            self.assertEqual(output.shape, torch.Size([5, 1]))

        def _create_torch_model(self):
            import torch.nn as nn

            class SimpleLinear(nn.Module):
                def __init__(self, input_dim, output_dim):
                    super(SimpleLinear, self).__init__()
                    self.linear = nn.Linear(input_dim, output_dim)

                def forward(self, x):
                    return self.linear(x)

            # Example usage
            model = SimpleLinear(input_dim=10, output_dim=1)
            return model

        def _test_torch_model(self, model):
            import torch

            x = torch.randn(5, 10)  # batch of 5 samples
            output = model(x)
            self.assertEqual(output.shape, torch.Size([5, 1]))
