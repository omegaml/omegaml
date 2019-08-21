import datetime
from unittest import TestCase

from omegaml import Omega
from omegaml.backends.virtualobj import VirtualObjectBackend, virtualobj, VirtualObjectHandler
from omegaml.mixins.store.virtualobj import VirtualObjectMixin
from omegaml.tests.util import OmegaTestMixin


class VirtualObjectTests(OmegaTestMixin, TestCase):
    def setUp(self):
        om = self.om = Omega()
        om.datasets.register_backend(VirtualObjectBackend.KIND, VirtualObjectBackend)
        om.datasets.register_mixin(VirtualObjectMixin)
        self.clean()

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

    def test_virtualhandler(self):
        om = self.om
        om.datasets.put(MyVirtualObjectHandler, 'virtualobj')
        entrymeta = om.datasets.put(['foo'], 'virtualobj')
        entrymeta = om.datasets.put(['bar'], 'virtualobj')
        self.assertEqual(entrymeta.name, 'virtualobj_data')

@virtualobj
def myvirtualfn(data=None, meta=None, method=None, store=None, **kwargs):
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