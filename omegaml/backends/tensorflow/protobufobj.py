from mongoengine import GridFSProxy

from omegaml import load_class
from omegaml.backends.basedata import BaseDataBackend


class ProtobufDataBackend(BaseDataBackend):
    KIND = 'protobuf.pbf'

    @classmethod
    def supports(self, obj, name, **kwargs):
        from google.protobuf.message import Message
        return isinstance(obj, Message)

    def put(self, obj, name, attributes=None, **kwargs):
        data = obj.SerializeToString()
        fileid = self.model_store.fs.put(data, filename=self.model_store._get_obj_store_key(name, '.pbf'))
        gridfile = GridFSProxy(grid_id=fileid,
                               db_alias='omega',
                               collection_name=self.model_store.bucket)
        kind_meta = {
            'protobuf_type': '{module}.{name}'.format(module=obj.DESCRIPTOR._concrete_class.__module__,
                                                      name=obj.DESCRIPTOR._concrete_class.__name__)
        }
        return self.model_store._make_metadata(
            name=name,
            prefix=self.model_store.prefix,
            bucket=self.model_store.bucket,
            kind=self.KIND,
            kind_meta=kind_meta,
            attributes=attributes,
            gridfile=gridfile).save()

    def get(self, name, version=-1, force_python=False, lazy=False, **kwargs):
        meta = self.data_store.metadata(name)
        data = meta.gridfile.read()
        # we get back a raw message, convert back to actual protobuf type
        # note the type must be loadable. will not work for arbitrary types
        pbtype = meta.kind_meta['protobuf_type']
        message = load_class(pbtype)()
        message.ParseFromString(data)
        return message

