from IPython.utils.tz import utcnow
from jupyter_server.services.contents.checkpoints import GenericCheckpointsMixin, Checkpoints


class NoOpCheckpoints(GenericCheckpointsMixin, Checkpoints):
    # source: https://jupyter-server.readthedocs.io/en/latest/developers/contents.html
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log.info("**** NoOpCheckpoints initialized")

    def checkpoint_model(self):
        info = {
            "id": "",
            "last_modified": utcnow()
        }
        return info

    def create_file_checkpoint(self, content, format, path):
        """ -> checkpoint model"""
        return self.checkpoint_model()

    def create_notebook_checkpoint(self, nb, path):
        """ -> checkpoint model"""
        return self.checkpoint_model()

    def get_file_checkpoint(self, checkpoint_id, path):
        """ -> {'type': 'file', 'content': <str>, 'format': {'text', 'base64'}}"""

    def get_notebook_checkpoint(self, checkpoint_id, path):
        """ -> {'type': 'notebook', 'content': <output of nbformat.read>}"""

    def delete_checkpoint(self, checkpoint_id, path):
        """deletes a checkpoint for a file"""

    def list_checkpoints(self, path):
        """returns a list of checkpoint models for a given file,
        default just does one per file
        """
        return []

    def rename_checkpoint(self, checkpoint_id, old_path, new_path):
        """renames checkpoint from old path to new path"""
