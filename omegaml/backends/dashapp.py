from io import BytesIO
from uuid import uuid4

import gridfs
from mongoengine import GridFSProxy

from dashserve import JupyterDash
from dashserve.serializer import DashAppSerializer
from omegaml.backends.basedata import BaseDataBackend


class DashAppBackend(BaseDataBackend):
    KIND = 'python.dash'

    @classmethod
    def supports(cls, obj, name, **kwargs):
        return isinstance(obj, JupyterDash)

    @property
    def _fs(self):
        return self.data_store.fs

    def _serializer(self, app=None):
        return DashAppSerializer(app)

    def put(self, obj, name, attributes=None, **kwargs):
        serialized = self._serializer(obj).serialize(wrap=False)
        bbuf = BytesIO(serialized)
        bbuf.seek(0)
        # see if we have a file already, if so replace the gridfile
        meta = self.data_store.metadata(name)
        if not meta:
            filename = uuid4().hex
            fileid = self._fs.put(bbuf, filename=filename)
            meta = self.data_store._make_metadata(name=name,
                                             prefix=self.data_store.prefix,
                                             bucket=self.data_store.bucket,
                                             kind=DashAppBackend.KIND,
                                             attributes=attributes,
                                             gridfile=GridFSProxy(grid_id=fileid))
        else:
            meta.gridfile.replace(bbuf)
        return meta.save()

    def get(self, name, **kwargs):
        """

        Args:
            name (str): the name of the dash app to load
            **kwargs: the kwargs to pass to DashappServe. Use to override
                      Dash kwargs

        Returns:
            Dashserve app i.e. deserialized dash server

        """
        meta = self.data_store.metadata(name)
        if meta:
            try:
                outf = meta.gridfile
            except gridfs.errors.NoFile as e:
                raise e
            serialized = outf.read()
            deserialized = self._serializer().deserialize(serialized, **kwargs)
        else:
            raise gridfs.errors.NoFile(
                ">{0}< does not exist in scripts bucket '{1}'".format(
                    name, self.data_store.bucket))
        return deserialized



