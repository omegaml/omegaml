import os

from omegajobs.omegacheckpoints import OmegaStoreContentsCheckpoints
from omegaml.notebook.omegacontentsmgr import OmegaStoreContentsManager


class OmegaStoreAuthenticatedContentsManager(OmegaStoreContentsManager):
    """
    Jupyter notebook storage manager for omegaml

    This requires a properly configured omegaml instance.

    see http://jupyter-notebook.readthedocs.io/en/stable/extending/contents.html
    """

    def _checkpoints_class_default(self):
        return OmegaStoreContentsCheckpoints

    @property
    def omega(self):
        """
        return the omega instance used by the contents manager
        """
        if self._omega is None:
            # if started from jupyter hub environ will be set
            userid = os.environ.get('JUPYTERHUB_USER')
            apikey = os.environ.get('OMEGA_APIKEY')
            if userid and apikey:
                from omegacommon.userconf import get_omega_from_apikey
                self._omega = get_omega_from_apikey(userid, apikey, view=True)
            else:
                import omegaml as om
                self._omega = om
        return self._omega
