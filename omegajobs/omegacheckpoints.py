import datetime

from bson.objectid import ObjectId
from notebook.services.contents.checkpoints import GenericCheckpointsMixin,\
    Checkpoints


class OmegaStoreContentsCheckpoints(GenericCheckpointsMixin, Checkpoints):

    def create_file_checkpoint(self, content, format, path):
        """Create a checkpoint of the current state of a file

        Returns a checkpoint model for the new checkpoint.
        """
        raise NotImplementedError("must be implemented in a subclass")

    def create_notebook_checkpoint(self, nb, path):
        """Create a checkpoint of the current state of a file

        Returns a checkpoint model for the new checkpoint.
        """
        coll = self.parent.store.collection('{}.ckp'.format(path))
        # FIXME transform content into base64, or store as a file
        #       this is because content can contain keys with . which are not supported by mongodb
        checkpoint = {
            'path': path,
            'last_modified': datetime.datetime.utcnow(),
            'content': nb,
        }
        cid = coll.insert(checkpoint)
        checkpoint['id'] = str(cid)
        del checkpoint['_id']
        return checkpoint

    def get_file_checkpoint(self, checkpoint_id, path):
        """Get the content of a checkpoint for a non-notebook file.

         Returns a dict of the form:
         {
             'type': 'file',
             'content': <str>,
             'format': {'text','base64'},
         }
        """
        raise NotImplementedError("must be implemented in a subclass")

    def get_notebook_checkpoint(self, checkpoint_id, path):
        """Get the content of a checkpoint for a notebook.

        Returns a dict of the form:
        {
            'type': 'notebook',
            'content': <output of nbformat.read>,
        }
        """
        coll = self.parent.store.collection('{}.ckp'.format(path))
        checkpoint = coll.find_one({'_id': ObjectId(checkpoint_id)})
        return checkpoint['content']

    def list_checkpoints(self, path):
        coll = self.parent.store.collection('{}.ckp'.format(path))
        return [dict(id=str(checkpoint['_id']),
                     last_modified=checkpoint.get('last_modified', datetime.datetime.utcnow()))
                for checkpoint in coll.find()]

    def delete_checkpoint(self, checkpoint_id, path):
        coll = self.parent.store.collection('{}.ckp'.format(path))
        coll.delete_one({'_id': ObjectId(checkpoint_id)})

    def rename_checkpoint(self, checkpoint_id, old_path, new_path):
        old_coll = self.parent.store.collection('{}.ckp'.format(old_path))
        checkpoint = old_coll.find_one({'_id': ObjectId(checkpoint_id)})
        new_coll = self.parent.store.collection('{}.ckp'.format(new_path))
        checkpoint['path'] = new_path
        cid = new_coll.insert(checkpoint)
        checkpoint['cid'] = str(cid)
        self.delete_checkpoint(checkpoint_id, old_path)
        del checkpoint['_id']
        return checkpoint
