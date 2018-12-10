from notebook.services.contents.checkpoints import GenericCheckpointsMixin, Checkpoints


class NoOpCheckpoints(GenericCheckpointsMixin, Checkpoints):
    # source https://jupyter-notebook.readthedocs.io/en/stable/extending/contents.html#customizing-checkpoints
    # © Copyright 2015, Jupyter Team, https://jupyter.org. Revision 775cb20d.

    def create_file_checkpoint(self, content, format, path):
        """ -> checkpoint model"""

    def create_notebook_checkpoint(self, nb, path):
        """ -> checkpoint model"""

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
