from unittest import TestCase

import datetime

from omegaml import Omega
from omegaml.backends.virtualobj import VirtualObjectBackend, virtualobj, VirtualObjectHandler
from omegaml.mixins.store.virtualobj import VirtualObjectMixin
from omegaml.tests.util import OmegaTestMixin


class VirtualObjectTests(OmegaTestMixin, TestCase):
    def setUp(self):
        om = self.om = Omega()
        om.datasets.register_backend(VirtualObjectBackend.KIND, VirtualObjectBackend)
        om.datasets.register_mixin(VirtualObjectMixin)
        om.scripts.register_backend(VirtualObjectBackend.KIND, VirtualObjectBackend)
        om.scripts.register_mixin(VirtualObjectMixin)
        self.clean()
        self.clean(bucket='test')

    def test_put(self):
        om = self.om
        meta = om.datasets.put(myvirtualfn, 'virtualobj')
        self.assertEqual(meta.kind, VirtualObjectBackend.KIND)

    def test_put_get(self):
        om = self.om
        meta = om.datasets.put(myvirtualfn, 'virtualobj')
        self.assertEqual(meta.kind, VirtualObjectBackend.KIND)
        # no data saved through the virtualobj yet
        data = om.datasets.get('virtualobj')
        self.assertEqual(data, 'no data yet')
        # save data
        entrymeta = om.datasets.put(['foo'], 'virtualobj')
        entrymeta = om.datasets.put(['bar'], 'virtualobj')
        self.assertEqual(entrymeta.name, 'virtualobj_data')
        self.assertEqual(entrymeta.attributes['virtualobj_ref'], 'virtualobj')
        meta = om.datasets.metadata('virtualobj')
        self.assertEqual(len(meta.attributes['real_data']), 2)
        data = om.datasets.get('virtualobj')
        self.assertEqual(data, [['foo'], ['bar']])

    def test_put_get_with_basename(self):
        om = self.om
        meta = om.datasets.put(myvirtualobjfn_with_basename, 'virtualobj')
        self.assertEqual(meta.kind, VirtualObjectBackend.KIND)
        # no data saved through the virtualobj yet
        data = om.datasets.get('virtualobj{base_name=foo_data}')
        self.assertEqual(data, 'no data yet')
        # save data
        entrymeta = om.datasets.put(['foo'], 'virtualobj{base_name=foo_data}')
        entrymeta = om.datasets.put(['bar'], 'virtualobj{base_name=foo_data}')
        self.assertEqual(entrymeta.name, 'foo_data')
        self.assertEqual(entrymeta.attributes['virtualobj_ref'], 'virtualobj')
        meta = om.datasets.metadata('virtualobj')
        self.assertEqual(len(meta.attributes['real_data']), 2)
        data = om.datasets.get('virtualobj{base_name=foo_data}')
        self.assertEqual(data, [['foo'], ['bar']])

    def test_drop(self):
        om = self.om
        meta = om.datasets.put(myvirtualfn, 'virtualobj')
        self.assertEqual(meta.kind, VirtualObjectBackend.KIND)
        self.assertTrue(om.datasets.drop('virtualobj'))

    def test_virtualhandler(self):
        om = self.om
        om.datasets.put(MyVirtualObjectHandler, 'virtualobj')
        entrymeta = om.datasets.put(['foo'], 'virtualobj')
        entrymeta = om.datasets.put(['bar'], 'virtualobj')
        self.assertEqual(entrymeta.name, 'virtualobj_data')

    def test_virtualobj_as_script(self):
        om = self.om

        @virtualobj
        def myscript(data=None, method=None, meta=None, store=None, tracking=None, **kwargs):
            if not data:
                raise ValueError(f'expected data, got {data}')
            return {'data': data, 'method': method}

        # working as expected
        om.scripts.put(myscript, 'myscript')
        # check myscript is actually deserialized by runtime
        myscript = None
        result = om.runtime.script('myscript').run({'foo': 'bar'})
        # expect a runtime error due to missing input
        with self.assertRaises(RuntimeError) as ex:
            om.runtime.script('myscript').run().get()

    def test_virtualobj_as_model(self):
        om = self.om

        @virtualobj
        def mymodel(data=None, method=None, meta=None, store=None, tracking=None, **kwargs):
            if not data:
                raise ValueError(f'expected data, got {data}')
            return {'data': data, 'method': method}

        # working as expected
        om.models.put(mymodel, 'mymodel')
        # check myscript is actually deserialized by runtime
        myscript = None
        result = om.runtime.model('mymodel').predict([42]).get()
        self.assertEqual(result.get('method'), 'predict')

    def test_virtualobj_promotion(self):
        om = self.om

        @virtualobj
        def mymodel(data=None, method=None, meta=None, store=None, tracking=None, **kwargs):
            if not data:
                raise ValueError(f'expected data, got {data}')
            return {'data': data, 'method': method}

        # working as expected
        meta = om.models.put(mymodel, 'mymodel', attributes={'foo': 'bar'})
        self.assertEqual(meta.attributes.get('foo'), 'bar')
        self.assertIn('versions', meta.attributes)
        other = om['target']
        # -- use export promotion, effectively copying 1:1
        other_meta = om.models.promote('mymodel', other.models, method='export')
        self.assertIsInstance(other_meta, other.models._Metadata)
        self.assertIn('mymodel', other.models.list())
        self.assertEqual(other_meta.attributes.get('foo'), 'bar')
        self.assertEqual(meta.attributes, other_meta.attributes)
        # -- use getput promotion, effectively creating a new version in other
        # -- check that meta.attributes other than 'versions' are promoted
        # -- check a new version is created
        meta.attributes['fox'] = 'bax'
        meta.save()
        other_meta = om.models.promote('mymodel', other.models, method='getput')
        self.assertNotEqual(meta.attributes.get('versions'),
                            other_meta.attributes.get('versions'))
        self.assertEqual(meta.attributes['fox'], other_meta.attributes['fox'])



@virtualobj
def myvirtualfn(data=None, meta=None, method=None, store=None, **kwargs):
    import datetime

    real_data_name = '{}_data'.format(meta.name)
    if method == 'get':
        data = store.get(real_data_name)
        return data or 'no data yet'
    if method == 'put':
        entrymeta = store.put(data, real_data_name, attributes={
            'virtualobj_ref': meta.name,
        })
        entrylist = meta.attributes.get('real_data', [])
        entrylist.append(datetime.datetime.now())
        meta.attributes['real_data'] = entrylist
        meta.save()
        return entrymeta
    if method == 'drop':
        store.drop(real_data_name, force=True)
        return 'ok, deleted'
    raise NotImplementedError


class MyVirtualObjectHandler(VirtualObjectHandler):
    def real_data_name(self, meta):
        return '{}_data'.format(meta.name)

    def get(self, data=None, meta=None, store=None, **kwargs):
        return store.get(self.real_data_name(meta)) or 'no data yet'

    def put(self, data=None, meta=None, store=None, **kwargs):
        import datetime
        entrymeta = store.put(data, self.real_data_name(meta), attributes={
            'virtualobj_ref': meta.name,
        })
        entrylist = meta.attributes.get('real_data', [])
        entrylist.append(datetime.datetime.now())
        meta.attributes['real_data'] = entrylist
        meta.save()
        return entrymeta

    def drop(self, data=None, meta=None, store=None, **kwargs):
        store.drop(self.real_data_name(meta), force=True)
        return 'ok, deleted'

@virtualobj
def myvirtualobjfn_with_basename(data=None, meta=None, method=None, base_name=None, store=None, **kwargs):
    import datetime
    real_data_name = base_name
    if method == 'get':
        data = store.get(real_data_name)
        return data or 'no data yet'
    if method == 'put':
        entrymeta = store.put(data, real_data_name, attributes={
            'virtualobj_ref': meta.name,
        })
        entrylist = meta.attributes.get('real_data', [])
        entrylist.append(datetime.datetime.now())
        meta.attributes['real_data'] = entrylist
        meta.save()
        return entrymeta
    if method == 'drop':
        store.drop(real_data_name, force=True)
        return 'ok, deleted'
    raise NotImplementedError
